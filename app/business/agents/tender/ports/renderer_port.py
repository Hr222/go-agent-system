from __future__ import annotations

from typing import Protocol

from app.business.agents.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderDocument,
)


class TenderSkeletonRendererPort(Protocol):
    """根据招标分析和源文档生成投标骨架文件的能力端口。"""

    def render(
        self,
        *,
        document: TenderDocument,
        analysis: TenderAnalysis,
    ) -> tuple[GeneratedTenderArtifact, ...]: ...

    def extract_range(
        self,
        *,
        document: TenderDocument,
        start_block_id: str,
        end_block_id: str,
        output_name: str,
    ) -> GeneratedTenderArtifact: ...
