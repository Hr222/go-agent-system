from __future__ import annotations

from app.modules.agent.tender.contracts import (
    TenderAnalysisBudget,
    TenderChunk,
    TenderChunkPlan,
    TenderDocument,
    TenderDocumentBlock,
)
from app.modules.agent.tender.errors import TenderAnalysisError


class TenderChunkPlanner:
    """按证据顺序、标题路径和表格边界组装分块。"""

    def plan(
        self, *, document: TenderDocument, budget: TenderAnalysisBudget
    ) -> TenderChunkPlan:
        if budget.chunk_input_chars < 128:
            raise TenderAnalysisError("分块输入预算过小，无法保留证据上下文。")

        chunks: list[TenderChunk] = []
        current: list[tuple[TenderDocumentBlock, str]] = []
        current_chars = 0

        def flush() -> None:
            nonlocal current, current_chars
            if not current:
                return
            sequence = len(chunks) + 1
            chunks.append(_make_chunk(sequence, current))
            current = []
            current_chars = 0

        for block in document.blocks:
            pieces = _block_pieces(block, budget.chunk_input_chars)
            for piece in pieces:
                piece_chars = len(piece)
                starts_new_section = bool(
                    current
                    and block.heading_level is not None
                    and block.heading_path != current[-1][0].heading_path
                )
                if starts_new_section or (
                    current and current_chars + piece_chars + 1 > budget.chunk_input_chars
                ):
                    flush()
                current.append((block, piece))
                current_chars += piece_chars + 1
                if len(chunks) >= budget.max_chunks:
                    raise TenderAnalysisError("招标文件分块数量超过分析预算。")
        flush()

        if not chunks:
            raise TenderAnalysisError("招标文件没有可用于分块分析的证据。")
        if len(chunks) > budget.max_chunks:
            raise TenderAnalysisError("招标文件分块数量超过分析预算。")
        return TenderChunkPlan(
            chunks=tuple(chunks),
            source_block_ids=tuple(block.block_id for block in document.blocks),
        )


def _block_pieces(block: TenderDocumentBlock, max_chars: int) -> list[str]:
    if block.kind != "table":
        return _split_text(block.text, max_chars)

    rows = block.table_rows
    if not rows:
        return _split_text(block.text, max_chars)
    if not block.text:
        block_text = _table_text(rows[0], list(rows[1:]))
        if len(block_text) <= max_chars:
            return [block_text]
    header = rows[0]
    header_text = " | ".join(header)
    pieces: list[str] = []
    current_rows: list[tuple[str, ...]] = []
    current_chars = len(header_text)
    for row in rows[1:] or rows:
        row_text = " | ".join(row)
        row_chars = len(row_text) + 3
        if current_rows and current_chars + row_chars > max_chars:
            pieces.append(_table_text(header, current_rows))
            current_rows = []
            current_chars = len(header_text)
        if not current_rows and current_chars + row_chars > max_chars:
            pieces.extend(_split_text(_table_text(header, [row]), max_chars))
            current_chars = len(header_text)
            continue
        current_rows.append(row)
        current_chars += row_chars
    if current_rows:
        pieces.append(_table_text(header, current_rows))
    return pieces


def _table_text(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    return " | ".join(
        " | ".join(row) for row in (header, *rows) if any(value.strip() for value in row)
    )


def _split_text(text: str, max_chars: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]
    pieces: list[str] = []
    remaining = normalized
    while remaining:
        if len(remaining) <= max_chars:
            pieces.append(remaining)
            break
        cut = max(
            remaining.rfind("\n", 0, max_chars),
            remaining.rfind("。", 0, max_chars),
            remaining.rfind("；", 0, max_chars),
            remaining.rfind(" ", 0, max_chars),
        )
        if cut < max_chars // 2:
            cut = max_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return pieces


def _make_chunk(sequence: int, items: list[tuple[TenderDocumentBlock, str]]) -> TenderChunk:
    evidence_ids = tuple(dict.fromkeys(block.block_id for block, _ in items))
    heading_path = next(
        (block.heading_path for block, _ in items if block.heading_path), ()
    )
    table_header = next(
        (block.table_header for block, _ in items if block.table_header), ()
    )
    text_parts = []
    for block, text in items:
        text_parts.append(
            f"[evidence_id={block.block_id}] [block_kind={block.kind}] {text}"
        )
    text = "\n".join(text_parts)
    return TenderChunk(
        chunk_id=f"chunk-{sequence:04d}",
        sequence=sequence,
        text=text,
        evidence_ids=evidence_ids,
        heading_path=heading_path,
        table_header=table_header,
        estimated_tokens=max(1, len(text) // 4),
    )
