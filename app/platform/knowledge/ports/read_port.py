from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

KnowledgeRetrievalMode = Literal["exact", "hnsw", "hybrid"]


@dataclass(slots=True, frozen=True)
class KnowledgeQuery:
    """知识查询用例的内部请求，不暴露 HTTP Schema。"""

    query: str
    top_k: int
    policy_category: str | None = None
    responsible_department: str | None = None
    document_id: int | None = None
    include_history: bool = False
    retrieval_mode: KnowledgeRetrievalMode = "hybrid"


@dataclass(slots=True, frozen=True)
class KnowledgeSearchHit:
    """知识查询返回的内部证据对象。"""

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
    rank: int
    retrieval_source: str
    source_path: str | None = None
    file_name: str | None = None
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class KnowledgeQueryTrace:
    name: str
    source: str | None = None
    input_count: int | None = None
    output_count: int | None = None
    details: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class KnowledgeQueryResult:
    query: str
    top_k: int
    policy_category: str | None
    responsible_department: str | None
    document_id: int | None
    include_history: bool
    hits: tuple[KnowledgeSearchHit, ...]
    pipeline: str
    strategy: str
    min_score: float
    traces: tuple[KnowledgeQueryTrace, ...] = ()


@dataclass(slots=True, frozen=True)
class KnowledgeDocument:
    document_id: int
    policy_name: str
    policy_category: str
    responsible_department: str | None
    latest_version_id: int | None
    latest_version_label: str | None


class KnowledgeReadPort(Protocol):
    """在线知识查询依赖的唯一读端口。"""

    def search(self, query: KnowledgeQuery) -> KnowledgeQueryResult: ...

    def list_documents(
        self,
        *,
        search: str | None = None,
        policy_category: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeDocument]: ...
