from __future__ import annotations

from app.platform.ingestion.contracts import (
    ChunkItem,
    ChunkSampleItem,
    ChunkSplitResult,
    SectionSplitResult,
)
from app.platform.ingestion.domain import PolicyChunkingPolicy
from app.shared.config import settings


class PolicyChunkingService:
    """负责流水线步骤 11：按章节继续切成可检索的 chunk。"""

    def __init__(self, chunking_policy: PolicyChunkingPolicy | None = None) -> None:
        self.chunking_policy = chunking_policy or PolicyChunkingPolicy(
            target_chars=settings.chunk_target_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )

    def split(
        self,
        section_result: SectionSplitResult,
        *,
        include_chunks: bool = True,
    ) -> ChunkSplitResult:
        """
        步骤 11：先保留 section 边界，再在 section 内做字符窗口切块。

        这里既生成完整 chunk，也顺手生成预览要用的 sample_chunks。
        """
        chunks: list[ChunkItem] = []
        for section in section_result.sections:
            slices = self.chunking_policy.split_section_text(section.section_text)
            if not slices:
                continue
            for slice_item in slices:
                metadata = {
                    "section_order": section.section_order,
                    "section_title": section.section_title,
                    "section_path": section.section_path,
                    "chunk_in_section": slice_item.chunk_in_section,
                    "chunk_start_offset": slice_item.start,
                    "chunk_end_offset": slice_item.end,
                    "source_block_start": section.source_block_start,
                    "source_block_end": section.source_block_end,
                }
                chunks.append(
                    ChunkItem(
                        chunk_index=len(chunks),
                        section_order=section.section_order,
                        section_title=section.section_title,
                        section_path=section.section_path,
                        chunk_text=slice_item.text,
                        chunk_in_section=slice_item.chunk_in_section,
                        chunk_start_offset=slice_item.start,
                        chunk_end_offset=slice_item.end,
                        char_count=len(slice_item.text),
                        page_no=section.page_start,
                        source_block_start=section.source_block_start,
                        source_block_end=section.source_block_end,
                        metadata=metadata,
                    )
                )

        sample_chunks = [
            ChunkSampleItem(
                section_title=item.section_title,
                section_path=item.section_path,
                chunk_preview=item.chunk_text[:180],
                char_count=item.char_count,
            )
            for item in chunks[:5]
        ]

        return ChunkSplitResult(
            total_chunks=len(chunks),
            strategy="section-first-char-window",
            notes=["先保留章节边界，再按字符长度切分过长章节。"],
            chunks=chunks if include_chunks else [],
            sample_chunks=sample_chunks,
        )
