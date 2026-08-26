from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.platform.knowledge.retrieval.contracts import RetrievalRepository, RetrievedPolicyChunk

VectorSearchStrategyName = Literal["exact", "hnsw"]


@dataclass(slots=True, frozen=True)
class VectorSearchRequest:
    """聚合向量召回所需参数，避免 pipeline 直接耦合仓储细节。"""

    query_embedding: list[float]
    top_k: int
    policy_category: str | None = None
    responsible_department: str | None = None
    document_id: int | None = None
    include_history: bool = False


class VectorSearchStrategy(Protocol):
    """约束向量召回策略的最小行为，便于后续接入 HNSW。"""

    strategy_name: VectorSearchStrategyName
    source_name: str

    def search(
        self,
        repository: RetrievalRepository,
        request: VectorSearchRequest,
    ) -> list[RetrievedPolicyChunk]: ...


class ExactVectorSearchStrategy:
    """当前默认向量召回策略：pgvector 精确余弦距离检索。"""

    strategy_name: VectorSearchStrategyName = "exact"
    source_name = "pgvector_cosine_exact"

    def search(
        self,
        repository: RetrievalRepository,
        request: VectorSearchRequest,
    ) -> list[RetrievedPolicyChunk]:
        return repository.search_chunks_exact(
            query_embedding=request.query_embedding,
            top_k=request.top_k,
            policy_category=request.policy_category,
            responsible_department=request.responsible_department,
            document_id=request.document_id,
            include_history=request.include_history,
        )


class HnswVectorSearchStrategy:
    """为后续 HNSW 接入预留统一策略入口。"""

    strategy_name: VectorSearchStrategyName = "hnsw"
    source_name = "pgvector_hnsw"

    def search(
        self,
        repository: RetrievalRepository,
        request: VectorSearchRequest,
    ) -> list[RetrievedPolicyChunk]:
        return repository.search_chunks_hnsw(
            query_embedding=request.query_embedding,
            top_k=request.top_k,
            policy_category=request.policy_category,
            responsible_department=request.responsible_department,
            document_id=request.document_id,
            include_history=request.include_history,
        )


def build_vector_search_strategy(
    strategy_name: VectorSearchStrategyName,
) -> VectorSearchStrategy:
    """按配置构造向量召回策略。"""

    if strategy_name == "exact":
        return ExactVectorSearchStrategy()
    if strategy_name == "hnsw":
        return HnswVectorSearchStrategy()
    raise ValueError(f"不支持的向量检索策略：{strategy_name}")
