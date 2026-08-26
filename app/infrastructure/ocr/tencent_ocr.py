from __future__ import annotations

import base64
import json
import mimetypes
from io import BytesIO
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.platform.ingestion.contracts import OcrProcessResult, ParsedBlock, ParsedDocumentResult
from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger("app.ocr.policy")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DIRECT_UPLOAD_MEDIA_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}
_CUSTOM_IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jpe": "image/jpeg",
    ".jp2": "image/jp2",
    ".jpx": "image/jp2",
}


def require_tencent_sdk() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.ocr.v20181119 import models, ocr_client
    except ImportError as exc:
        raise RuntimeError(
            "缺少腾讯 OCR SDK，请先安装 tencentcloud-sdk-python。"
        ) from exc

    return credential, ClientProfile, HttpProfile, models, ocr_client


class PolicyOcrService:
    """处理扫描页和图片块的 OCR。"""

    _rate_limit_lock = Lock()
    _next_request_at = 0.0

    def __init__(self, client: object | None = None, tencent_models: object | None = None) -> None:
        self._client_injected = client is not None
        self._pdf_base64_cache: dict[str, str] = {}
        self.tencent_models = tencent_models

        if client is not None:
            self.client = client
        else:
            self.client, self.tencent_models = self._build_tencent_client()
        self.request_interval_seconds = max(0.0, settings.ocr_request_interval_seconds)

    def process(self, document: ParsedDocumentResult, *, persist: bool) -> OcrProcessResult:
        ocr_targets = self._select_ocr_targets(document)
        if not ocr_targets:
            return OcrProcessResult(
                applied=False,
                parse_method="direct",
                blocks=document.blocks,
                notes=self._build_skip_notes(document),
                failed_blocks=0,
            )

        if not settings.ocr_enabled:
            notes = ["OCR 已禁用，当前文档保留直接解析结果。"]
            if persist:
                notes.append("入库模式下需要 OCR 的文档将被后续阶段拦截。")
            return OcrProcessResult(
                applied=False,
                parse_method="direct",
                blocks=document.blocks,
                notes=notes,
                failed_blocks=len(ocr_targets),
            )

        if not self._client_injected and not self._has_provider_credentials():
            return OcrProcessResult(
                applied=False,
                parse_method="direct",
                blocks=document.blocks,
                notes=[self._missing_provider_credentials_message()],
                failed_blocks=len(ocr_targets),
            )

        updated_blocks: list[ParsedBlock] = []
        failed_blocks = 0
        succeeded_blocks = 0
        skipped_blank_blocks = 0
        target_ids = {block.block_id for block in ocr_targets}

        for block in document.blocks:
            if block.block_id not in target_ids:
                updated_blocks.append(block)
                continue

            try:
                if block.metadata.get("pdf_page_render"):
                    image_bytes = b""
                else:
                    image_bytes, _ = self._resolve_image_payload(document.source_path, block)
                normalized_text = self._ocr_image_bytes(
                    image_bytes,
                    block_id=block.block_id,
                    page_no=block.page_no,
                    source_path=document.source_path,
                    block=block,
                ).strip()
                persistable_metadata = self._strip_runtime_image_metadata(block.metadata)
                if normalized_text:
                    updated_blocks.append(
                        block.model_copy(
                            update={
                                "text": normalized_text,
                                "source": "ocr",
                                "metadata": persistable_metadata,
                            }
                        )
                    )
                    succeeded_blocks += 1
                else:
                    failed_blocks += 1
                    updated_blocks.append(
                        block.model_copy(update={"metadata": persistable_metadata})
                    )
            except Exception as exc:
                if self._is_expected_no_text_error(exc):
                    skipped_blank_blocks += 1
                    updated_blocks.append(
                        block.model_copy(
                            update={"metadata": self._strip_runtime_image_metadata(block.metadata)}
                        )
                    )
                    logger.info(
                        "OCR skipped blank page/textless block block_id=%s page_no=%s provider=%s",
                        block.block_id,
                        block.page_no,
                        "tencent",
                    )
                    continue
                logger.exception(
                    "OCR request failed block_id=%s page_no=%s",
                    block.block_id,
                    block.page_no,
                )
                failed_blocks += 1
                updated_blocks.append(
                    block.model_copy(
                        update={"metadata": self._strip_runtime_image_metadata(block.metadata)}
                    )
                )

        parse_method: str = "direct"
        if succeeded_blocks and failed_blocks:
            parse_method = "mixed"
        elif succeeded_blocks:
            parse_method = "ocr" if document.suspected_scanned else "mixed"

        notes = [
            f"OCR 处理完成：成功 {succeeded_blocks} 个图片块，失败 {failed_blocks} 个图片块。"
        ]
        if skipped_blank_blocks:
            notes.append(f"已跳过 {skipped_blank_blocks} 个空白页/无文本图片块。")
        if failed_blocks and persist:
            notes.append("部分图片块 OCR 失败；若无法形成有效正文，入库阶段会终止。")

        # 上游 OCR 分支只会产生 direct / ocr / mixed 三种受支持值，
        # 此处保留类型检查豁免，避免把运行期解析结果重复转换成另一套 DTO。
        return OcrProcessResult(
            applied=succeeded_blocks > 0,
            parse_method=parse_method,  # type: ignore[arg-type]
            blocks=updated_blocks,
            notes=notes,
            failed_blocks=failed_blocks,
        )

    def _select_ocr_targets(self, document: ParsedDocumentResult) -> list[ParsedBlock]:
        image_blocks = [block for block in document.blocks if block.block_type == "image"]
        if not image_blocks:
            return []

        if document.file_type == "image":
            return [block for block in image_blocks if block.metadata.get("image_bytes")]

        if document.file_type == "docx":
            return [block for block in image_blocks if block.metadata.get("image_bytes")]

        if document.file_type != "pdf":
            return []

        if document.suspected_scanned:
            page_render_blocks = [
                block for block in image_blocks if bool(block.metadata.get("pdf_page_render"))
            ]
            if page_render_blocks:
                return page_render_blocks

        return [block for block in image_blocks if block.metadata.get("image_bytes")]

    def _build_skip_notes(self, document: ParsedDocumentResult) -> list[str]:
        image_blocks = [block for block in document.blocks if block.block_type == "image"]
        if not image_blocks:
            return ["当前文档未检测到需要 OCR 的图片块。"]
        if document.file_type == "image":
            return ["当前图片文件未形成可执行的 OCR 目标。"]
        if document.file_type == "docx":
            return ["当前 DOCX 缺少可用于 OCR 的图片块。"]
        if document.file_type == "pdf" and not document.suspected_scanned:
            return ["当前 PDF 缺少可用于 OCR 的内嵌图片块。"]
        return ["当前文档无需执行 OCR。"]

    def _has_effective_text(self, document: ParsedDocumentResult) -> bool:
        return any(
            block.block_type in {"text", "table"}
            and (block.text or "").strip()
            and block.metadata.get("has_effective_text", True)
            for block in document.blocks
        )

    def _resolve_image_payload(self, source_path: str, block: ParsedBlock) -> tuple[bytes, str]:
        if block.metadata.get("pdf_page_render"):
            return self._render_pdf_page_as_png_bytes(source_path, block.page_no), "image/png"

        if not block.metadata.get("image_bytes"):
            raise RuntimeError("当前图片块缺少可用于 OCR 的图像内容。")

        image_bytes = bytes.fromhex(block.metadata["image_bytes"])
        media_type = self._resolve_media_type(block, image_bytes)
        return self._normalize_image_payload(image_bytes, media_type)

    def _ocr_image_bytes(
        self,
        image_bytes: bytes,
        *,
        block_id: str | None = None,
        page_no: int | None = None,
        source_path: str | None = None,
        block: ParsedBlock | None = None,
    ) -> str:
        if block is not None and block.metadata.get("pdf_page_render"):
            return self._ocr_pdf_page_with_tencent(source_path=source_path, page_no=page_no)
        return self._ocr_image_bytes_with_tencent(
            image_bytes,
            block_id=block_id,
            page_no=page_no,
        )

    def _ocr_image_bytes_with_tencent(
        self,
        image_bytes: bytes,
        *,
        block_id: str | None = None,
        page_no: int | None = None,
    ) -> str:
        response_json = self._call_tencent_ocr(
            payload={"ImageBase64": base64.b64encode(image_bytes).decode("utf-8")},
            block_id=block_id,
            page_no=page_no,
        )
        return "\n".join(self._extract_tencent_lines(response_json)).strip()

    def _ocr_pdf_page_with_tencent(
        self,
        *,
        source_path: str | None,
        page_no: int | None,
    ) -> str:
        if not source_path:
            raise RuntimeError("腾讯 OCR 缺少 PDF 文件路径。")
        if page_no is None:
            raise RuntimeError("腾讯 OCR 缺少 PDF 页码。")

        response_json = self._call_tencent_ocr(
            payload={
                "ImageBase64": self._load_pdf_base64(source_path),
                "IsPdf": True,
                "PdfPageNumber": page_no,
            },
            page_no=page_no,
        )
        return "\n".join(self._extract_tencent_lines(response_json)).strip()

    def _render_pdf_page_as_png_bytes(self, source_path: str, page_no: int | None) -> bytes:
        if page_no is None:
            raise RuntimeError("扫描页图片块缺少页码，无法渲染 PDF 页面。")
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("缺少依赖：未安装 PyMuPDF。") from exc

        document = fitz.open(source_path)
        try:
            page = document.load_page(page_no - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return pix.tobytes("png")
        finally:
            document.close()

    def _strip_runtime_image_metadata(self, metadata: dict) -> dict:
        return {
            key: value
            for key, value in metadata.items()
            if key not in {"image_bytes", "pdf_page_render"}
        }

    def _has_provider_credentials(self) -> bool:
        return bool(settings.tencent_ocr_secret_id and settings.tencent_ocr_secret_key)

    def _missing_provider_credentials_message(self) -> str:
        return "未配置 TENCENT_OCR_SECRET_ID / TENCENT_OCR_SECRET_KEY，无法执行 OCR。"

    def _build_tencent_client(self) -> tuple[object, object]:
        credential, ClientProfile, HttpProfile, models, ocr_client = require_tencent_sdk()
        if not settings.tencent_ocr_secret_id or not settings.tencent_ocr_secret_key:
            raise RuntimeError(self._missing_provider_credentials_message())

        cred = credential.Credential(
            settings.tencent_ocr_secret_id,
            settings.tencent_ocr_secret_key,
        )
        http_profile = HttpProfile()
        http_profile.endpoint = settings.tencent_ocr_endpoint
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client = ocr_client.OcrClient(cred, settings.tencent_ocr_region, client_profile)
        return client, models

    def _call_tencent_ocr(
        self,
        *,
        payload: dict[str, object],
        block_id: str | None = None,
        page_no: int | None = None,
    ) -> dict[str, object]:
        if self.tencent_models is None:
            raise RuntimeError("腾讯 OCR SDK 未初始化。")

        request_name = f"{settings.tencent_ocr_action}Request"
        request_cls = getattr(self.tencent_models, request_name, None)
        if request_cls is None:
            raise RuntimeError(f"腾讯 OCR 不支持的动作：{settings.tencent_ocr_action}")

        request = request_cls()
        request.from_json_string(json.dumps(payload))
        self._reserve_request_slot(block_id=block_id, page_no=page_no)
        response = getattr(self.client, settings.tencent_ocr_action)(request)
        response_json = json.loads(response.to_json_string())
        logger.info(
            "OCR raw response provider=tencent action=%s block_id=%s page_no=%s response=%s",
            settings.tencent_ocr_action,
            block_id,
            page_no,
            json.dumps(response_json, ensure_ascii=False),
        )
        return response_json

    def _extract_tencent_lines(self, response_json: dict[str, object]) -> list[str]:
        detections = response_json.get("TextDetections", [])
        if not isinstance(detections, list):
            return []

        lines: list[str] = []
        for item in detections:
            if not isinstance(item, dict):
                continue
            text = item.get("DetectedText")
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
        return lines

    def _load_pdf_base64(self, source_path: str) -> str:
        cached = self._pdf_base64_cache.get(source_path)
        if cached is not None:
            return cached

        encoded = base64.b64encode(Path(source_path).read_bytes()).decode("utf-8")
        self._pdf_base64_cache[source_path] = encoded
        return encoded

    def _is_expected_no_text_error(self, exc: Exception) -> bool:
        error_code = getattr(exc, "code", None)
        if error_code == "FailedOperation.ImageNoText":
            return True
        return False

    def _reserve_request_slot(
        self,
        *,
        block_id: str | None = None,
        page_no: int | None = None,
    ) -> None:
        if self.request_interval_seconds <= 0:
            return

        with self._rate_limit_lock:
            now = monotonic()
            wait_seconds = max(0.0, self._next_request_at - now)
            scheduled_at = max(now, self._next_request_at)
            self.__class__._next_request_at = scheduled_at + self.request_interval_seconds

        if wait_seconds > 0:
            logger.info(
                "OCR request throttled block_id=%s page_no=%s "
                "wait_seconds=%.2f interval_seconds=%.2f",
                block_id,
                page_no,
                wait_seconds,
                self.request_interval_seconds,
            )
            sleep(wait_seconds)

    def _resolve_media_type(self, block: ParsedBlock, image_bytes: bytes) -> str:
        explicit_media_type = block.metadata.get("image_media_type")
        if isinstance(explicit_media_type, str) and explicit_media_type.startswith("image/"):
            return explicit_media_type

        image_name = block.metadata.get("image_name")
        guessed_by_name = self._guess_media_type_from_name(image_name)
        if guessed_by_name is not None:
            return guessed_by_name

        guessed_by_bytes = self._guess_media_type_from_bytes(image_bytes)
        if guessed_by_bytes is not None:
            return guessed_by_bytes

        return "application/octet-stream"

    def _normalize_image_payload(self, image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
        if media_type == "image/png" and image_bytes.startswith(_PNG_SIGNATURE):
            return image_bytes, media_type

        if media_type in _DIRECT_UPLOAD_MEDIA_TYPES:
            return image_bytes, media_type

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                buffer = BytesIO()
                image.save(buffer, format="PNG")
        except (UnidentifiedImageError, OSError) as exc:
            raise RuntimeError("图片无法转换为 OCR 可识别格式。") from exc

        return buffer.getvalue(), "image/png"

    def _guess_media_type_from_name(self, image_name: object) -> str | None:
        if not isinstance(image_name, str) or not image_name:
            return None

        suffix = Path(image_name).suffix.lower()
        if suffix in _CUSTOM_IMAGE_MEDIA_TYPES:
            return _CUSTOM_IMAGE_MEDIA_TYPES[suffix]

        guessed_type, _ = mimetypes.guess_type(image_name)
        return guessed_type

    def _guess_media_type_from_bytes(self, image_bytes: bytes) -> str | None:
        if image_bytes.startswith(_PNG_SIGNATURE):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_bytes.startswith(b"BM"):
            return "image/bmp"
        if image_bytes.startswith((b"II*\x00", b"MM\x00*")):
            return "image/tiff"
        if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return None
