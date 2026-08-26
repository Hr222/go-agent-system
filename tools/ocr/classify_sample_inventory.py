from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.platform.ingestion.pipeline.scan_service import PolicyIngestionService


@dataclass(slots=True)
class PdfTextSignal:
    total_pages: int
    sampled_pages: int
    nonempty_sampled_pages: int
    total_sampled_text_chars: int
    page_text_lengths: list[int]
    pdf_kind: str
    error: str | None = None


@dataclass(slots=True)
class BusinessValueLabel:
    knowledge_route: str
    rag_suitability: str
    business_reason: str


@dataclass(slots=True)
class InventoryItem:
    source_path: str
    relative_path: str
    file_name: str
    extension: str
    size_bytes: int
    recommended_action: str
    parse_method: str
    pipeline_bucket: str
    suspected_scanned: bool
    top_level_group: str
    policy_name_guess: str
    reason: str | None
    knowledge_route: str
    rag_suitability: str
    business_reason: str
    pdf_signal: PdfTextSignal | None = None


EXCLUDE_LOW_VALUE_KEYWORDS = {
    "logo",
    "照片",
    "截图",
    "签字",
    "签名",
    "身份证",
    "公章",
    "印章",
    "空白",
    "模板",
    "收款码",
}

RAG_HIGH_KEYWORDS = {
    "章程": "章程/制度类文档文字密度高，适合 OCR 后切块进入 RAG。",
    "制度": "制度类文档以连续文本为主，适合进入 RAG 文本库。",
    "业主评价": "业主评价通常是自然语言内容，适合进入 RAG。",
    "评价": "评价/说明类材料通常以自然语言为主，适合进入 RAG。",
    "历史评估报告": "历史评估报告具备较强上下文，适合进入 RAG。",
    "评估报告": "报告正文通常以段落文字为主，适合进入 RAG。",
    "文章": "专业文章适合按段落切块后进入 RAG。",
    "专业期刊": "专业文章适合按段落切块后进入 RAG。",
    "公司简介": "公司简介类材料适合做语义检索。",
    "简介": "简介说明类材料适合做语义检索。",
}

RAG_MEDIUM_KEYWORDS = {
    "收费标准": "收费标准可以进入 RAG，但更适合短片段检索。",
    "报价": "报价说明可进入 RAG，但通常只覆盖局部问答。",
    "可研": "可研/说明文档可进入 RAG，但需要后续清洗。",
    "方案": "方案说明类文件具备上下文，可作为中等优先级 RAG 语料。",
}

STRUCTURED_LOW_KEYWORDS = {
    "资质": "资质证书更适合抽取证书名称、编号、有效期等字段。",
    "证书": "证书/证明类材料更适合结构化字段抽取。",
    "资格": "资格证通常以字段检索为主，不建议直接作为 RAG 主语料。",
    "备案": "备案函/备案证明更适合抽取编号、日期、主体信息。",
    "证明": "证明类文件以关键字段为主，更适合结构化处理。",
    "执照": "营业执照类材料更适合字段抽取。",
    "社保": "社保/纳税类证明更适合字段核验与结构化抽取。",
    "纳税": "社保/纳税类证明更适合字段核验与结构化抽取。",
    "信用": "信用查询报告更适合作为测试样本或结构化信息来源。",
    "查询": "查询/检索结果页通常是字段列表，不是当前 RAG 主语料。",
    "记录": "记录/台账类材料更适合做结构化检索。",
    "排名": "排名/榜单类文件以字段展示为主，更适合结构化使用。",
    "估价师": "估价师查询结果更适合字段抽取。",
    "荣誉": "荣誉证书更适合结构化抽取。",
    "获奖": "荣誉证书更适合结构化抽取。",
    "营业执照": "营业执照类材料更适合字段抽取。",
}

STRUCTURED_MEDIUM_KEYWORDS = {
    "组织架构": "组织架构更像图表/关系信息，优先考虑结构化抽取。",
    "架构图": "架构图更适合结构化关系抽取，不是当前 RAG 主力。",
    "流程图": "流程图更适合做结构化节点关系抽取。",
    "财务报告": "财务报告往往以表格和数字为主，更适合结构化处理。",
    "人员资格": "人员资格类资料更适合字段核验。",
    "人员名单": "名单/名册更适合结构化检索。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "样本资料分类脚本。递归扫描目录，并将文件粗分为直接解析、"
            "先转 DOCX、需 OCR、排除或人工复核，同时补充业务价值标签。"
        )
    )
    parser.add_argument("source_root", help="待扫描的资料根目录。")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="可选：指定输出目录。默认写入 .runtime/ocr_inventory/<时间戳>_<目录名>/",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="可选：限制本次最多扫描多少个文件。0 表示扫描全部文件。",
    )
    parser.add_argument(
        "--pdf-sample-pages",
        type=int,
        default=3,
        help="可选：PDF 文本探测时抽样前多少页。默认 3 页。",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=10,
        help="可选：终端预览多少条重点记录。默认 10 条。",
    )
    return parser.parse_args()


def analyze_pdf_text(path: Path, sample_pages: int = 3) -> PdfTextSignal:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        return PdfTextSignal(
            total_pages=0,
            sampled_pages=0,
            nonempty_sampled_pages=0,
            total_sampled_text_chars=0,
            page_text_lengths=[],
            pdf_kind="unknown",
            error=f"missing dependency: {exc}",
        )

    try:
        reader = PdfReader(str(path))
        total_pages = len(reader.pages)
        sampled_pages = min(max(sample_pages, 1), total_pages)
        page_text_lengths: list[int] = []
        for page in reader.pages[:sampled_pages]:
            text = (page.extract_text() or "").strip()
            page_text_lengths.append(len(text))

        nonempty_sampled_pages = sum(1 for length in page_text_lengths if length > 0)
        total_sampled_text_chars = sum(page_text_lengths)

        if sampled_pages == 0:
            pdf_kind = "empty"
        elif nonempty_sampled_pages == 0:
            pdf_kind = "scanned"
        elif nonempty_sampled_pages == sampled_pages:
            pdf_kind = "text"
        else:
            pdf_kind = "mixed"

        return PdfTextSignal(
            total_pages=total_pages,
            sampled_pages=sampled_pages,
            nonempty_sampled_pages=nonempty_sampled_pages,
            total_sampled_text_chars=total_sampled_text_chars,
            page_text_lengths=page_text_lengths,
            pdf_kind=pdf_kind,
        )
    # 单个 PDF 抽样失败时返回可展示的错误信号，不阻断整个目录分类任务。 pragma: no cover
    except Exception as exc:  # pragma: no cover
        return PdfTextSignal(
            total_pages=0,
            sampled_pages=0,
            nonempty_sampled_pages=0,
            total_sampled_text_chars=0,
            page_text_lengths=[],
            pdf_kind="error",
            error=str(exc),
        )


def classify_business_value(
    *,
    relative_path: str,
    top_level_group: str,
    policy_name_guess: str,
    pipeline_bucket: str,
) -> BusinessValueLabel:
    normalized = " ".join([relative_path, top_level_group, policy_name_guess]).lower()

    if pipeline_bucket == "exclude":
        return BusinessValueLabel(
            knowledge_route="exclude_low_value",
            rag_suitability="low",
            business_reason="当前文件已在技术筛选阶段排除，不建议进入 RAG 或结构化流程。",
        )

    for keyword in EXCLUDE_LOW_VALUE_KEYWORDS:
        if keyword.lower() in normalized:
            return BusinessValueLabel(
                knowledge_route="exclude_low_value",
                rag_suitability="low",
                business_reason="文件更像低价值附件或素材图片，不建议进入知识库。",
            )

    for keyword, reason in STRUCTURED_LOW_KEYWORDS.items():
        if keyword.lower() in normalized:
            return BusinessValueLabel(
                knowledge_route="structured_fields",
                rag_suitability="low",
                business_reason=reason,
            )

    for keyword, reason in STRUCTURED_MEDIUM_KEYWORDS.items():
        if keyword.lower() in normalized:
            return BusinessValueLabel(
                knowledge_route="structured_fields",
                rag_suitability="medium",
                business_reason=reason,
            )

    for keyword, reason in RAG_HIGH_KEYWORDS.items():
        if keyword.lower() in normalized:
            return BusinessValueLabel(
                knowledge_route="rag_text",
                rag_suitability="high",
                business_reason=reason,
            )

    for keyword, reason in RAG_MEDIUM_KEYWORDS.items():
        if keyword.lower() in normalized:
            return BusinessValueLabel(
                knowledge_route="rag_text",
                rag_suitability="medium",
                business_reason=reason,
            )

    if pipeline_bucket in {"direct_parse", "ocr", "convert_doc_to_docx"}:
        return BusinessValueLabel(
            knowledge_route="review_business",
            rag_suitability="medium",
            business_reason=(
                "技术上可处理，但业务归类不够明确，建议人工判断是进入 RAG 还是结构化流程。"
            ),
        )

    return BusinessValueLabel(
        knowledge_route="exclude_low_value",
        rag_suitability="low",
        business_reason="当前文件不建议作为首批知识库样本。",
    )


def classify_file(
    *,
    root: Path,
    path: Path,
    service: PolicyIngestionService,
    pdf_sample_pages: int,
) -> InventoryItem:
    extension = path.suffix.lower()
    relative_path = str(path.relative_to(root))
    full_text = f"{path.name} {relative_path}"
    size_bytes = path.stat().st_size
    top_level_group = Path(relative_path).parts[0] if Path(relative_path).parts else path.name
    suspected_scanned = extension in service._image_extensions or (
        extension == ".pdf" and service._contains_keyword(full_text, service._scanned_keywords)
    )

    recommended_action = "exclude"
    parse_method = "skip"
    pipeline_bucket = "exclude"
    reason: str | None = None
    pdf_signal: PdfTextSignal | None = None

    if size_bytes == 0:
        reason = "空文件，先排除。"
    elif extension in service._excluded_extensions:
        reason = "压缩包不在当前样本接入范围内。"
    elif service._contains_keyword(full_text, service._excluded_keywords):
        reason = "命中排除关键词，建议先跳过。"
    elif extension not in service._supported_extensions:
        reason = "当前分类脚本仅覆盖 doc/docx/pdf 和常见图片文件。"
    elif extension == ".doc":
        recommended_action = "include"
        parse_method = "doc"
        pipeline_bucket = "convert_doc_to_docx"
        reason = "老旧 .doc 文件，建议先借助 WPS 转成 .docx 再解析。"
    elif extension in service._image_extensions:
        recommended_action = "include"
        parse_method = "ocr"
        pipeline_bucket = "ocr"
        reason = "图片型样本，直接进入 OCR 流程。"
    elif extension == ".pdf":
        pdf_signal = analyze_pdf_text(path, sample_pages=pdf_sample_pages)
        if suspected_scanned or pdf_signal.pdf_kind == "scanned":
            recommended_action = "include"
            parse_method = "ocr"
            pipeline_bucket = "ocr"
            suspected_scanned = True
            reason = "PDF 抽样页提不到文本，建议走 OCR。"
        elif pdf_signal.pdf_kind == "text":
            recommended_action = "include"
            parse_method = "direct"
            pipeline_bucket = "direct_parse"
            reason = "PDF 抽样页可稳定提取文本，建议直接解析。"
        elif pdf_signal.pdf_kind == "mixed":
            recommended_action = "review"
            parse_method = "review"
            pipeline_bucket = "review"
            reason = "PDF 既有文本页也有疑似扫描页，建议人工复核后决定走直解析还是 OCR。"
        else:
            recommended_action = "review"
            parse_method = "review"
            pipeline_bucket = "review"
            reason = "PDF 文本探测失败，建议人工复核。"
    else:
        recommended_action = "include"
        parse_method = "direct"
        pipeline_bucket = "direct_parse"
        reason = "原生 Office 文本文件，可直接进入解析流程。"

    business_label = classify_business_value(
        relative_path=relative_path,
        top_level_group=top_level_group,
        policy_name_guess=service._guess_policy_name(path.stem),
        pipeline_bucket=pipeline_bucket,
    )

    return InventoryItem(
        source_path=str(path),
        relative_path=relative_path,
        file_name=path.name,
        extension=extension,
        size_bytes=size_bytes,
        recommended_action=recommended_action,
        parse_method=parse_method,
        pipeline_bucket=pipeline_bucket,
        suspected_scanned=suspected_scanned,
        top_level_group=top_level_group,
        policy_name_guess=service._guess_policy_name(path.stem),
        reason=reason,
        knowledge_route=business_label.knowledge_route,
        rag_suitability=business_label.rag_suitability,
        business_reason=business_label.business_reason,
        pdf_signal=pdf_signal,
    )


def build_output_dir(source_root: Path, output_dir: str | None) -> Path:
    if output_dir:
        target = Path(output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = source_root.name.replace(" ", "_")
        target = Path(".runtime/ocr_inventory") / f"{stamp}_{safe_name}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_csv(items: list[InventoryItem], output_path: Path) -> None:
    fieldnames = [
        "top_level_group",
        "relative_path",
        "file_name",
        "extension",
        "size_bytes",
        "recommended_action",
        "parse_method",
        "pipeline_bucket",
        "knowledge_route",
        "rag_suitability",
        "suspected_scanned",
        "policy_name_guess",
        "reason",
        "business_reason",
        "pdf_kind",
        "pdf_total_pages",
        "pdf_sampled_pages",
        "pdf_nonempty_sampled_pages",
        "pdf_total_sampled_text_chars",
        "pdf_page_text_lengths",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            pdf_signal = item.pdf_signal
            writer.writerow(
                {
                    "top_level_group": item.top_level_group,
                    "relative_path": item.relative_path,
                    "file_name": item.file_name,
                    "extension": item.extension,
                    "size_bytes": item.size_bytes,
                    "recommended_action": item.recommended_action,
                    "parse_method": item.parse_method,
                    "pipeline_bucket": item.pipeline_bucket,
                    "knowledge_route": item.knowledge_route,
                    "rag_suitability": item.rag_suitability,
                    "suspected_scanned": item.suspected_scanned,
                    "policy_name_guess": item.policy_name_guess,
                    "reason": item.reason or "",
                    "business_reason": item.business_reason,
                    "pdf_kind": pdf_signal.pdf_kind if pdf_signal else "",
                    "pdf_total_pages": pdf_signal.total_pages if pdf_signal else "",
                    "pdf_sampled_pages": pdf_signal.sampled_pages if pdf_signal else "",
                    "pdf_nonempty_sampled_pages": (
                        pdf_signal.nonempty_sampled_pages if pdf_signal else ""
                    ),
                    "pdf_total_sampled_text_chars": (
                        pdf_signal.total_sampled_text_chars if pdf_signal else ""
                    ),
                    "pdf_page_text_lengths": (
                        ",".join(str(length) for length in pdf_signal.page_text_lengths)
                        if pdf_signal
                        else ""
                    ),
                }
            )


def write_summary(
    *,
    source_root: Path,
    output_dir: Path,
    items: list[InventoryItem],
) -> Path:
    by_extension = Counter(item.extension or "<none>" for item in items)
    by_bucket = Counter(item.pipeline_bucket for item in items)
    by_action = Counter(item.recommended_action for item in items)
    by_knowledge_route = Counter(item.knowledge_route for item in items)
    by_rag_suitability = Counter(item.rag_suitability for item in items)
    by_top_level: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in items:
        by_top_level[item.top_level_group]["total"] += 1
        by_top_level[item.top_level_group][item.pipeline_bucket] += 1
        by_top_level[item.top_level_group][item.knowledge_route] += 1

    summary = {
        "source_root": str(source_root),
        "scanned_at": datetime.now(UTC).isoformat(),
        "total_files": len(items),
        "stats": {
            "by_extension": dict(sorted(by_extension.items())),
            "by_bucket": dict(sorted(by_bucket.items())),
            "by_action": dict(sorted(by_action.items())),
            "by_knowledge_route": dict(sorted(by_knowledge_route.items())),
            "by_rag_suitability": dict(sorted(by_rag_suitability.items())),
            "by_top_level_group": {
                key: dict(sorted(value.items())) for key, value in sorted(by_top_level.items())
            },
        },
        "items": [
            {
                **asdict(item),
                "pdf_signal": asdict(item.pdf_signal) if item.pdf_signal else None,
            }
            for item in items
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def preview_items(items: list[InventoryItem], preview: int) -> None:
    focus_items = [
        item
        for item in items
        if item.pipeline_bucket in {"ocr", "review", "convert_doc_to_docx"}
        or item.knowledge_route in {"rag_text", "structured_fields", "review_business"}
    ]
    if preview <= 0 or not focus_items:
        return

    print("重点样本预览：")
    for item in focus_items[:preview]:
        signal = item.pdf_signal.pdf_kind if item.pdf_signal else "-"
        print(
            f"- [{item.pipeline_bucket}/{item.knowledge_route}] {item.relative_path} | "
            f"parse={item.parse_method} | rag={item.rag_suitability} | pdf_kind={signal}"
        )


def main() -> None:
    args = parse_args()
    source_root = Path(args.source_root).expanduser().resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"扫描目录不存在：{source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"扫描路径不是目录：{source_root}")

    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    if args.limit > 0:
        files = files[: args.limit]

    service = PolicyIngestionService()
    items = [
        classify_file(
            root=source_root,
            path=path,
            service=service,
            pdf_sample_pages=max(1, args.pdf_sample_pages),
        )
        for path in files
    ]

    output_dir = build_output_dir(source_root, args.output_dir)
    summary_path = write_summary(source_root=source_root, output_dir=output_dir, items=items)
    csv_path = output_dir / "items.csv"
    write_csv(items, csv_path)

    by_bucket = Counter(item.pipeline_bucket for item in items)
    by_knowledge_route = Counter(item.knowledge_route for item in items)
    print(f"分类完成：{source_root}")
    print(f"输出目录：{output_dir}")
    print(f"摘要文件：{summary_path}")
    print(f"明细文件：{csv_path}")
    print(
        "技术分类统计："
        f" total={len(items)}"
        f", direct_parse={by_bucket.get('direct_parse', 0)}"
        f", convert_doc_to_docx={by_bucket.get('convert_doc_to_docx', 0)}"
        f", ocr={by_bucket.get('ocr', 0)}"
        f", review={by_bucket.get('review', 0)}"
        f", exclude={by_bucket.get('exclude', 0)}"
    )
    print(
        "业务分类统计："
        f" rag_text={by_knowledge_route.get('rag_text', 0)}"
        f", structured_fields={by_knowledge_route.get('structured_fields', 0)}"
        f", review_business={by_knowledge_route.get('review_business', 0)}"
        f", exclude_low_value={by_knowledge_route.get('exclude_low_value', 0)}"
    )
    preview_items(items, args.preview)


if __name__ == "__main__":
    main()
