from __future__ import annotations

from dataclasses import replace

from app.interfaces.http.schemas import RetrievalSearchRequest
from app.platform.knowledge.retrieval import HybridRetrievalPipeline
from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk


class StubEmbeddingService:
    def embed_query(self, query: str) -> list[float]:
        assert query
        return [0.1, 0.2, 0.3]


class StubRepository:
    def __init__(
        self,
        *,
        vector_hits: list[RetrievedPolicyChunk],
        keyword_hits: list[RetrievedPolicyChunk],
    ) -> None:
        self._vector_hits = vector_hits
        self._keyword_hits = keyword_hits

    def search_chunks_exact(self, **kwargs) -> list[RetrievedPolicyChunk]:
        return [replace(hit) for hit in self._vector_hits]

    def search_chunks_hnsw(self, **kwargs) -> list[RetrievedPolicyChunk]:
        raise AssertionError("Milestone C Step C2 默认不应走 HNSW 召回。")

    def search_chunks(self, **kwargs) -> list[RetrievedPolicyChunk]:
        return [replace(hit) for hit in self._vector_hits]

    def search_chunks_by_keywords(self, **kwargs) -> list[RetrievedPolicyChunk]:
        return [replace(hit) for hit in self._keyword_hits]


def _hit(
    *,
    chunk_id: int,
    section_title: str,
    chunk_text: str,
    score: float,
    retrieval_source: str = "hybrid",
    vector_score: float = 0.0,
    keyword_score: float = 0.0,
) -> RetrievedPolicyChunk:
    score_breakdown = {}
    if vector_score > 0.0:
        score_breakdown["vector"] = vector_score
    if keyword_score > 0.0:
        score_breakdown["keyword"] = keyword_score

    return RetrievedPolicyChunk(
        document_id=1,
        version_id=1,
        chunk_id=chunk_id,
        policy_name="示例管理制度",
        policy_category="人事制度",
        responsible_department="人力资源部",
        version_label="2025",
        section_title=section_title,
        section_path=f"第一章 / 总则 / {section_title}",
        page_no=1,
        chunk_text=chunk_text,
        score=score,
        retrieval_source=retrieval_source,
        score_breakdown=score_breakdown,
        debug_details={},
    )


def test_rerank_promotes_scope_clause_to_top1() -> None:
    # 合成适用范围问题：第二条虽然原始融合分略低，但正文更直接回答问题。
    pipeline = HybridRetrievalPipeline(
        repository=object(),
        embedding_service=StubEmbeddingService(),
    )
    keyword_plan = pipeline.query_policy.build_keyword_plan("管理制度适用于哪些人")
    hits = [
        _hit(
            chunk_id=1,
            section_title="第一条",
            chunk_text="为规范公司人事管理，建立统一管理秩序，制定本制度。",
            score=0.92,
            vector_score=0.78,
            keyword_score=0.88,
        ),
        _hit(
            chunk_id=2,
            section_title="第二条",
            chunk_text="本制度适用于公司全体员工，包括试用期员工和正式员工。",
            score=0.84,
            vector_score=0.72,
            keyword_score=0.80,
        ),
    ]

    reranked_hits = pipeline._rerank_hits(
        query="管理制度适用于哪些人",
        keyword_plan=keyword_plan,
        hits=hits,
    )

    assert reranked_hits[0].chunk_id == 2
    assert reranked_hits[0].score_breakdown["rerank"] > reranked_hits[1].score_breakdown["rerank"]
    assert reranked_hits[0].debug_details["rerank_matched_fields"] == "chunk_text, policy_name"


def test_rerank_keeps_trial_period_clause_above_irrelevant_article() -> None:
    # 模拟 HR-002 风格问题：真正写明试用期时长的条款，应压过无关的制度尾部条款。
    pipeline = HybridRetrievalPipeline(
        repository=object(),
        embedding_service=StubEmbeddingService(),
    )
    keyword_plan = pipeline.query_policy.build_keyword_plan("员工试用期多久")
    hits = [
        _hit(
            chunk_id=61,
            section_title="第六十一条",
            chunk_text="本制度自发布之日起生效，解释权归公司所有。",
            score=0.88,
            vector_score=0.80,
            keyword_score=0.84,
        ),
        _hit(
            chunk_id=5,
            section_title="第五条",
            chunk_text="员工试用期为六个月，试用期包含在劳动合同期限内。",
            score=0.81,
            vector_score=0.73,
            keyword_score=0.79,
        ),
    ]

    reranked_hits = pipeline._rerank_hits(
        query="员工试用期多久",
        keyword_plan=keyword_plan,
        hits=hits,
    )

    assert reranked_hits[0].chunk_id == 5
    assert reranked_hits[0].score_breakdown["rerank"] == 1.0
    assert reranked_hits[1].score_breakdown["rerank"] == 0.0


def test_pipeline_run_emits_rerank_stage_and_score_breakdown() -> None:
    # 除了顺序变化，还要验证 pipeline 对外暴露了 rerank 阶段与分数拆解。
    shared_vector_hit = _hit(
        chunk_id=2,
        section_title="第二条",
        chunk_text="本制度适用于公司全体员工，包括试用期员工和正式员工。",
        score=0.78,
        retrieval_source="vector",
        vector_score=0.78,
    )
    shared_keyword_hit = _hit(
        chunk_id=2,
        section_title="第二条",
        chunk_text="本制度适用于公司全体员工，包括试用期员工和正式员工。",
        score=0.80,
        retrieval_source="keyword",
        keyword_score=0.80,
    )
    repository = StubRepository(
        vector_hits=[
            _hit(
                chunk_id=1,
                section_title="第一条",
                chunk_text="为规范公司人事管理，建立统一管理秩序，制定本制度。",
                score=0.82,
                retrieval_source="vector",
                vector_score=0.82,
            ),
            shared_vector_hit,
        ],
        keyword_hits=[shared_keyword_hit],
    )
    pipeline = HybridRetrievalPipeline(
        repository=repository,
        embedding_service=StubEmbeddingService(),
    )

    result = pipeline.run(
        RetrievalSearchRequest(
        query="管理制度适用于哪些人",
            top_k=5,
        )
    )

    assert [trace.name for trace in result.traces] == [
        "query_embedding",
        "vector_recall",
        "keyword_recall",
        "result_fusion",
        "rerank",
        "score_filter",
    ]
    assert result.hits[0].chunk_id == 2
    assert result.hits[0].retrieval_source == "hybrid"
    assert "rerank" in result.hits[0].score_breakdown
