from __future__ import annotations

import argparse
import base64
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.modules.ingestion.pipeline.steps.policy_parser import PolicyParserService


class TencentOcrMvpSettings(BaseSettings):
    """腾讯 OCR MVP 脚本配置。"""

    secret_id: str | None = Field(default=None, alias="TENCENT_OCR_SECRET_ID")
    secret_key: str | None = Field(default=None, alias="TENCENT_OCR_SECRET_KEY")
    region: str = Field(default="ap-guangzhou", alias="TENCENT_OCR_REGION")
    endpoint: str = Field(default="ocr.tencentcloudapi.com", alias="TENCENT_OCR_ENDPOINT")
    action: str = Field(default="GeneralAccurateOCR", alias="TENCENT_OCR_ACTION")
    output_root: str = Field(default=".runtime/ocr_output", alias="TENCENT_OCR_OUTPUT_ROOT")
    docx_image_limit: int = Field(default=50, alias="TENCENT_OCR_DOCX_IMAGE_LIMIT")
    pdf_page_limit: int = Field(default=0, alias="TENCENT_OCR_PDF_PAGE_LIMIT")
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )


@dataclass(slots=True)
class OcrSliceResult:
    source_kind: str
    source_name: str
    page_or_index: int
    text_line_count: int
    text_preview: str
    raw_response_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "腾讯 OCR MVP 测试脚本。支持 PDF 扫描件按页识别，也支持从 DOCX 中提取图片后逐张识别。"
        )
    )
    parser.add_argument("input_path", help="待识别的 PDF 或 DOCX 文件路径。")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="可选：指定输出目录。默认写入 .runtime/ocr_output/<时间戳>_<文件名>/",
    )
    parser.add_argument(
        "--page-start",
        type=int,
        default=1,
        help="PDF 起始页码，从 1 开始。默认 1。",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="可选：限制本次最多识别多少页 PDF。默认取环境变量或全部。",
    )
    parser.add_argument(
        "--docx-image-limit",
        type=int,
        default=None,
        help="可选：限制本次最多识别多少张 DOCX 图片。默认取环境变量或全部。",
    )
    return parser.parse_args()


def require_tencent_sdk() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
            TencentCloudSDKException,
        )
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.ocr.v20181119 import models, ocr_client
    except ImportError as exc:
        raise RuntimeError(
            "缺少腾讯云 OCR SDK。请先安装 requirements-dev.txt，"
            "或单独执行 `pip install tencentcloud-sdk-python`。"
        ) from exc

    return credential, TencentCloudSDKException, ClientProfile, HttpProfile, models, ocr_client


def build_ocr_client(settings: TencentOcrMvpSettings) -> tuple[Any, Any]:
    (
        credential,
        _sdk_exception_cls,
        ClientProfile,
        HttpProfile,
        models,
        ocr_client,
    ) = require_tencent_sdk()

    if not settings.secret_id or not settings.secret_key:
        raise RuntimeError(
            "未配置 TENCENT_OCR_SECRET_ID / TENCENT_OCR_SECRET_KEY，无法调用腾讯 OCR。"
        )

    # 这里沿用腾讯云 OCR 官方 Python SDK demo 的建 client 方式：
    # Credential -> HttpProfile -> ClientProfile -> OcrClient。
    cred = credential.Credential(settings.secret_id, settings.secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = settings.endpoint
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = ocr_client.OcrClient(cred, settings.region, client_profile)
    return client, models


def encode_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def call_general_accurate_ocr(
    *,
    client: Any,
    models: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # 这里沿用腾讯云 OCR 官方 demo 的请求构造方式：
    # request.from_json_string(json.dumps(payload))
    request = models.GeneralAccurateOCRRequest()
    request.from_json_string(json.dumps(payload))
    response = client.GeneralAccurateOCR(request)
    return json.loads(response.to_json_string())


def extract_detected_lines(response_json: dict[str, Any]) -> list[str]:
    detections = response_json.get("TextDetections", [])
    lines: list[str] = []
    if not isinstance(detections, list):
        return lines

    for item in detections:
        if not isinstance(item, dict):
            continue
        text = item.get("DetectedText")
        if isinstance(text, str) and text.strip():
            lines.append(text.strip())
    return lines


def build_output_dir(
    input_path: Path, output_dir: str | None, settings: TencentOcrMvpSettings
) -> Path:
    if output_dir:
        target = Path(output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = input_path.stem.replace(" ", "_")
        target = Path(settings.output_root) / f"{stamp}_{safe_name}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def run_pdf_mvp(
    *,
    input_path: Path,
    output_dir: Path,
    client: Any,
    models: Any,
    page_start: int,
    page_limit: int,
) -> list[OcrSliceResult]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少依赖：未安装 pypdf。") from exc

    if page_start < 1:
        raise ValueError("page_start 必须从 1 开始。")

    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise RuntimeError("PDF 没有可识别页。")

    effective_start = min(page_start, total_pages)
    effective_end = total_pages
    if page_limit > 0:
        effective_end = min(total_pages, effective_start + page_limit - 1)

    pdf_base64 = encode_file_base64(input_path)
    results: list[OcrSliceResult] = []

    for page_number in range(effective_start, effective_end + 1):
        response_json = call_general_accurate_ocr(
            client=client,
            models=models,
            payload={
                "ImageBase64": pdf_base64,
                "IsPdf": True,
                "PdfPageNumber": page_number,
            },
        )
        response_path = output_dir / f"pdf_page_{page_number:03d}.json"
        response_path.write_text(
            json.dumps(response_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        lines = extract_detected_lines(response_json)
        preview = "\n".join(lines[:5])[:300]
        results.append(
            OcrSliceResult(
                source_kind="pdf",
                source_name=input_path.name,
                page_or_index=page_number,
                text_line_count=len(lines),
                text_preview=preview,
                raw_response_file=str(response_path),
            )
        )

    return results


def run_docx_mvp(
    *,
    input_path: Path,
    output_dir: Path,
    client: Any,
    models: Any,
    image_limit: int,
) -> list[OcrSliceResult]:
    parsed = PolicyParserService().parse_document(
        source_path=str(input_path),
        parse_method="direct",
    )
    image_blocks = [
        block
        for block in parsed.blocks
        if block.block_type == "image" and block.metadata.get("image_bytes")
    ]
    if not image_blocks:
        raise RuntimeError("DOCX 中未检测到可供 OCR 识别的图片块。")

    if image_limit > 0:
        image_blocks = image_blocks[:image_limit]

    results: list[OcrSliceResult] = []
    for index, block in enumerate(image_blocks, start=1):
        image_hex = block.metadata.get("image_bytes")
        if not isinstance(image_hex, str) or not image_hex:
            continue

        response_json = call_general_accurate_ocr(
            client=client,
            models=models,
            payload={
                "ImageBase64": base64.b64encode(bytes.fromhex(image_hex)).decode("utf-8"),
            },
        )
        response_path = output_dir / f"docx_image_{index:03d}.json"
        response_path.write_text(
            json.dumps(response_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        lines = extract_detected_lines(response_json)
        preview = "\n".join(lines[:5])[:300]
        image_name = str(block.metadata.get("image_name") or f"image-{index}")
        results.append(
            OcrSliceResult(
                source_kind="docx-image",
                source_name=image_name,
                page_or_index=index,
                text_line_count=len(lines),
                text_preview=preview,
                raw_response_file=str(response_path),
            )
        )

    return results


def write_summary(
    *,
    input_path: Path,
    output_dir: Path,
    settings: TencentOcrMvpSettings,
    results: list[OcrSliceResult],
) -> Path:
    summary_path = output_dir / "summary.json"
    summary = {
        "input_file": str(input_path),
        "ocr_action": settings.action,
        "region": settings.region,
        "slice_count": len(results),
        "results": [asdict(item) for item in results],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def main() -> None:
    args = parse_args()
    settings = TencentOcrMvpSettings()
    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在：{input_path}")
    if not input_path.is_file():
        raise IsADirectoryError(f"输入路径不是文件：{input_path}")

    suffix = input_path.suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValueError("当前 MVP 脚本仅支持 .pdf 和 .docx 输入。")

    output_dir = build_output_dir(input_path, args.output_dir, settings)
    client, models = build_ocr_client(settings)

    if settings.action != "GeneralAccurateOCR":
        raise ValueError("当前 MVP 脚本仅封装腾讯 OCR 的 GeneralAccurateOCR。")

    if suffix == ".pdf":
        resolved_page_limit = (
            args.page_limit if args.page_limit is not None else settings.pdf_page_limit
        )
        results = run_pdf_mvp(
            input_path=input_path,
            output_dir=output_dir,
            client=client,
            models=models,
            page_start=args.page_start,
            page_limit=max(0, resolved_page_limit),
        )
    else:
        resolved_image_limit = (
            args.docx_image_limit
            if args.docx_image_limit is not None
            else settings.docx_image_limit
        )
        results = run_docx_mvp(
            input_path=input_path,
            output_dir=output_dir,
            client=client,
            models=models,
            image_limit=max(0, resolved_image_limit),
        )

    summary_path = write_summary(
        input_path=input_path,
        output_dir=output_dir,
        settings=settings,
        results=results,
    )

    print(f"OCR 完成：{input_path.name}")
    print(f"输出目录：{output_dir}")
    print(f"摘要文件：{summary_path}")
    for item in results:
        print(
            f"- {item.source_kind} #{item.page_or_index}: "
            f"{item.text_line_count} lines | {item.raw_response_file}"
        )


if __name__ == "__main__":
    main()
