from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
from typing import Literal

CandidateRetrievalStatus = Literal["ready", "empty", "unavailable"]
IndexBuildStatus = Literal["ready", "empty", "failed"]


class CandidateIndexError(ValueError):
    """候选索引数据不满足向量检索契约。"""


@dataclass(frozen=True, slots=True)
class CapabilityCandidateIndexEntry:
    """能力候选索引中的一条记录，只通过稳定能力代码关联目录。"""

    capability_code: str
    search_text: str
    vector: tuple[float, ...]
    retrieval_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.capability_code.strip():
            raise CandidateIndexError("候选索引记录缺少能力代码。")
        if not self.search_text.strip():
            raise CandidateIndexError("候选索引记录缺少检索文本。")
        _validate_vector(self.vector)


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    """返回给后续意图识别层的候选，不包含可执行对象。"""

    capability_code: str
    score: float
    retrieval_metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CapabilityCandidateRetrievalResult:
    """一次候选查询的显式结果。"""

    query: str
    status: CandidateRetrievalStatus
    candidates: tuple[CapabilityCandidate, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityIndexBuildResult:
    """一次目录索引构建的显式结果。"""

    status: IndexBuildStatus
    indexed_count: int
    error_code: str | None = None
    error_message: str | None = None


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """计算两个已验证向量的余弦相似度。"""

    _validate_vector(left)
    _validate_vector(right)
    if len(left) != len(right):
        raise CandidateIndexError("候选向量维度不一致。")
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise CandidateIndexError("候选向量不能是零向量。")
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (
        left_norm * right_norm
    )


def _validate_vector(vector: tuple[float, ...]) -> None:
    if not vector or any(not isfinite(value) for value in vector):
        raise CandidateIndexError("候选向量必须是非空有限数字序列。")
