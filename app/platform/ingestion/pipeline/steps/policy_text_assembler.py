from __future__ import annotations

import re

from app.platform.ingestion.contracts import AssembledLine, ParsedDocumentResult, ParsedTextResult

CHINESE_HEADING_PATTERNS = (
    r"^第[一二三四五六七八九十百千万零〇两0-9]+章.*$",
    r"^第[一二三四五六七八九十百千万零〇两0-9]+节.*$",
    r"^第[一二三四五六七八九十百千万零〇两0-9]+条.*$",
)


class PolicyTextAssemblerService:
    """按 block 顺序组装全文文本。"""

    def assemble(self, document: ParsedDocumentResult, *, parse_method: str) -> ParsedTextResult:
        lines: list[AssembledLine] = []
        paragraphs: list[str] = []
        tables: list[str] = []
        notes = list(document.notes)
        inline_ocr_text = self._collect_inline_ocr_text(document)

        # 空 block 文档不应在组装阶段抛异常，保持可预期的空文本结果，
        # 让后续入库拦截或预览提示按正常分支处理。
        page_count = None
        if document.blocks:
            page_count = max((block.page_no or 0) for block in document.blocks) or None

        for block in document.blocks:
            # page_break 只负责分页边界，不参与正文拼装。
            if block.block_type == "page_break":
                continue

            if block.block_type == "image" and block.metadata.get("placeholder_token"):
                continue

            resolved_text = self._resolve_inline_placeholders(block.text or "", inline_ocr_text)
            if not resolved_text.strip():
                continue

            block_lines = [line.strip() for line in resolved_text.splitlines() if line.strip()]
            if not block_lines:
                continue

            if block.block_type == "table":
                tables.extend(block_lines)
            else:
                paragraphs.extend(block_lines)

            # OCR 文本和直接解析文本都必须按原始 block 顺序回填，
            # 这样章节拆分和来源追踪才能保持稳定。
            for line in block_lines:
                lines.append(
                    AssembledLine(
                        text=line,
                        page_no=block.page_no,
                        source_block_order=block.order,
                    )
                )

        raw_text = "\n".join(line.text for line in lines)

        return ParsedTextResult(
            parser_status=document.parser_status,
            source_path=document.source_path,
            parse_method=parse_method,  # type: ignore[arg-type]
            raw_text=raw_text,
            page_count=page_count,
            suspected_scanned=document.suspected_scanned,
            lines=lines,
            paragraphs=paragraphs,
            tables=tables,
            title_candidates=self._detect_title_candidates([line.text for line in lines]),
            notes=notes,
        )

    def _detect_title_candidates(self, paragraphs: list[str]) -> list[str]:
        compiled = [re.compile(pattern) for pattern in CHINESE_HEADING_PATTERNS]
        titles: list[str] = []
        for paragraph in paragraphs:
            if any(pattern.match(paragraph) for pattern in compiled):
                titles.append(paragraph)
            if len(titles) >= 30:
                break
        return titles

    def _collect_inline_ocr_text(self, document: ParsedDocumentResult) -> dict[str, str]:
        inline_ocr_text: dict[str, str] = {}
        for block in document.blocks:
            placeholder_token = block.metadata.get("placeholder_token")
            if isinstance(placeholder_token, str):
                inline_ocr_text[placeholder_token] = (block.text or "").strip()
        return inline_ocr_text

    def _resolve_inline_placeholders(
        self,
        text: str,
        inline_ocr_text: dict[str, str],
    ) -> str:
        resolved_text = text
        for placeholder_token, ocr_text in inline_ocr_text.items():
            resolved_text = resolved_text.replace(placeholder_token, ocr_text)
        return re.sub(r"\[IMAGE_OCR_\d+\]", "", resolved_text)
