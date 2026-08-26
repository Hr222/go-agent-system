from __future__ import annotations

from typing import Protocol

from app.business.agents.tender.contracts import (
    TenderAnalysis,
    TenderAnalysisBudget,
    TenderChunk,
    TenderChunkAnalysis,
    TenderChunkPlan,
    TenderDocument,
)
from app.platform.llm.contracts import StructuredLlmPort


class TenderChunkPlannerPort(Protocol):
    """在不调用 LLM 的情况下生成有序、有限大小的证据分块。"""

    def plan(
        self, *, document: TenderDocument, budget: TenderAnalysisBudget
    ) -> TenderChunkPlan: ...


class TenderChunkAnalyzerPort(Protocol):
    """从单个分块提取局部要求。"""

    def analyze(self, *, chunk: TenderChunk) -> TenderChunkAnalysis: ...


class TenderAnalysisMergerPort(Protocol):
    """将局部结果有界归并为最终 TenderAnalysis。"""

    def merge(
        self, *, items: tuple[TenderChunkAnalysis | TenderAnalysis, ...]
    ) -> TenderAnalysis: ...


__all__ = [
    "StructuredLlmPort",
    "TenderChunkAnalyzerPort",
    "TenderChunkPlannerPort",
    "TenderAnalysisMergerPort",
]
