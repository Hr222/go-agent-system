from __future__ import annotations

from dataclasses import dataclass, field

from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk


@dataclass(slots=True)
class RetrievalStageTrace:
    """记录检索各阶段的输入、输出与调试细节。"""

    name: str
    source: str | None = None
    input_count: int | None = None
    output_count: int | None = None
    details: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalPipelineResult:
    """聚合检索 pipeline 的最终结果与调试轨迹。"""

    hits: list[RetrievedPolicyChunk]
    pipeline: str
    strategy: str
    min_score: float
    traces: list[RetrievalStageTrace]
