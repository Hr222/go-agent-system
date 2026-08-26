from __future__ import annotations

from app.business.online.application.rag_facade import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    RagApplicationFacade,
)
from app.business.online.contracts import AnswerResult, AskKnowledgeCommand
from app.interfaces.http.assemblers.rag import search_response
from app.platform.knowledge.application.query_capability import KnowledgeBaseQueryCapability
from app.platform.knowledge.ports.read_port import (
    KnowledgeQueryResult,
    KnowledgeSearchHit,
)


def _make_hit() -> KnowledgeSearchHit:
    return KnowledgeSearchHit(
        document_id=101,
        version_id=201,
        chunk_id=301,
        policy_name="示例制度",
        policy_category="管理制度",
        responsible_department=None,
        version_label="现行",
        section_title="第一条",
        section_path="第一条",
        page_no=1,
        chunk_text="这是用于测试的制度片段。",
        score=1.0,
        rank=1,
        retrieval_source="hybrid",
        source_path="D:/knowledge/示例制度.docx",
        file_name="示例制度.docx",
        score_breakdown={"keyword": 1.0},
    )


def _make_result(hits: tuple[KnowledgeSearchHit, ...]) -> KnowledgeQueryResult:
    return KnowledgeQueryResult(
        query="测试问题",
        top_k=5,
        policy_category="管理制度",
        responsible_department=None,
        document_id=None,
        include_history=False,
        hits=hits,
        pipeline="test-pipeline",
        strategy="test-strategy",
        min_score=0.45,
    )


class FakeReadPort:
    def __init__(self, result: KnowledgeQueryResult) -> None:
        self.result = result
        self.search_call_count = 0

    def search(self, query):  # noqa: ANN001
        self.search_call_count += 1
        return self.result

    def list_documents(self, **kwargs):  # noqa: ANN003
        return []


class FakeAnswerGenerator:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer
        self.call_count = 0

    def answer(self, *, query: str, hits: list[KnowledgeSearchHit]) -> AnswerResult:
        self.call_count += 1
        return AnswerResult(
            query=query,
            answer=self.answer_text,
            model="fake-model",
            citations=(),
            hits=tuple(hits),
            knowledge=None,
        )


def _make_facade(
    *,
    hits: tuple[KnowledgeSearchHit, ...],
    answer: str = "这是回答。",
) -> tuple[RagApplicationFacade, FakeReadPort, FakeAnswerGenerator]:
    read_port = FakeReadPort(_make_result(hits))
    answer_generator = FakeAnswerGenerator(answer)
    facade = RagApplicationFacade(
        knowledge_query=KnowledgeBaseQueryCapability(read_port),
        answer_generator=answer_generator,
    )
    return facade, read_port, answer_generator


def test_facade_searches_before_generating_answer() -> None:
    facade, read_port, answer_generator = _make_facade(hits=(_make_hit(),))

    response = facade.ask(AskKnowledgeCommand(query="测试问题", top_k=5))

    assert read_port.search_call_count == 1
    assert answer_generator.call_count == 1
    assert response.answer == "这是回答。"
    assert response.knowledge is not None
    assert response.hits[0].source_path == "D:/knowledge/示例制度.docx"
    assert response.hits[0].file_name == "示例制度.docx"


def test_search_response_exposes_source_trace_fields() -> None:
    response = search_response(_make_result((_make_hit(),)))

    assert response.hits[0].source_path == "D:/knowledge/示例制度.docx"
    assert response.hits[0].file_name == "示例制度.docx"


def test_facade_returns_insufficient_evidence_without_answer_generation() -> None:
    facade, read_port, answer_generator = _make_facade(hits=())

    response = facade.ask(AskKnowledgeCommand(query="测试问题", top_k=5))

    assert read_port.search_call_count == 1
    assert answer_generator.call_count == 0
    assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert response.hits == ()
