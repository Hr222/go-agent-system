from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class RetrievedPolicyChunk:
    """检索层与持久化适配器之间的最小查询结果契约。"""

    document_id: int
    version_id: int
    chunk_id: int
    policy_name: str
    policy_category: str
    responsible_department: str | None
    version_label: str
    section_title: str | None
    section_path: str | None
    page_no: int | None
    chunk_text: str
    score: float
    source_path: str | None = None
    file_name: str | None = None
    retrieval_source: str = "vector"
    score_breakdown: dict[str, float] = field(default_factory=dict)
    debug_details: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class RetrievalRepository(Protocol):
    """约束检索 pipeline 依赖的仓储能力，避免直接耦合具体实现细节。"""

    def search_chunks_exact(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        policy_category: str | None = None,
        responsible_department: str | None = None,
        document_id: int | None = None,
        include_history: bool = False,
    ) -> list[RetrievedPolicyChunk]: ...

    def search_chunks_hnsw(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        policy_category: str | None = None,
        responsible_department: str | None = None,
        document_id: int | None = None,
        include_history: bool = False,
    ) -> list[RetrievedPolicyChunk]: ...

    def search_chunks(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        policy_category: str | None = None,
        responsible_department: str | None = None,
        document_id: int | None = None,
        include_history: bool = False,
    ) -> list[RetrievedPolicyChunk]: ...

    def search_chunks_by_keywords(
        self,
        *,
        focus_query: str | None,
        keywords: list[str],
        priority_keywords: list[str] | None = None,
        top_k: int,
        policy_category: str | None = None,
        responsible_department: str | None = None,
        document_id: int | None = None,
        include_history: bool = False,
    ) -> list[RetrievedPolicyChunk]: ...


class QueryEmbeddingService(Protocol):
    """约束查询向量服务，只保留 pipeline 真正关心的接口。"""

    def embed_query(self, query: str) -> list[float]: ...
