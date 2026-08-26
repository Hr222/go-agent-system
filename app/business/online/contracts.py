from __future__ import annotations

from dataclasses import dataclass

from app.business.online.domain.citation import AnswerCitationResult
from app.platform.knowledge.ports.read_port import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeRetrievalMode,
    KnowledgeSearchHit,
)


@dataclass(slots=True, frozen=True)
class AskKnowledgeCommand:
    query: str
    top_k: int
    policy_category: str | None = None
    responsible_department: str | None = None
    document_id: int | None = None
    include_history: bool = False
    retrieval_mode: KnowledgeRetrievalMode = "hybrid"

    def as_knowledge_query(self) -> KnowledgeQuery:
        return KnowledgeQuery(
            query=self.query,
            top_k=self.top_k,
            policy_category=self.policy_category,
            responsible_department=self.responsible_department,
            document_id=self.document_id,
            include_history=self.include_history,
            retrieval_mode=self.retrieval_mode,
        )


@dataclass(slots=True, frozen=True)
class AnswerResult:
    query: str
    answer: str
    model: str | None
    citations: tuple[AnswerCitationResult, ...]
    hits: tuple[KnowledgeSearchHit, ...]
    knowledge: KnowledgeQueryResult | None
