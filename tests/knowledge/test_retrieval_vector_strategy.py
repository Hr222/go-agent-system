from __future__ import annotations

from app.interfaces.http.schemas import RetrievalSearchRequest
from app.platform.knowledge.retrieval import (
    ExactVectorSearchStrategy,
    HnswVectorSearchStrategy,
    HybridRetrievalPipeline,
    build_vector_search_strategy,
)
from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk
from app.shared.config import settings


class StubEmbeddingService:
    def embed_query(self, query: str) -> list[float]:
        assert query
        return [0.1, 0.2, 0.3]


class TrackingRepository:
    def __init__(self) -> None:
        self.called_strategy: str | None = None
        self.keyword_calls = 0

    def search_chunks_exact(self, **kwargs) -> list[RetrievedPolicyChunk]:
        self.called_strategy = "exact"
        return [
            RetrievedPolicyChunk(
                document_id=1,
                version_id=1,
                chunk_id=1,
                policy_name="人事管理制度",
                policy_category="人事制度",
                responsible_department="人力资源部",
                version_label="2025",
                section_title="第二条",
                section_path="总则 / 第二条",
                page_no=1,
                chunk_text="本制度适用于公司全体员工。",
                score=0.88,
                retrieval_source="vector",
                score_breakdown={"vector": 0.88},
                debug_details={},
            )
        ]

    def search_chunks_hnsw(self, **kwargs) -> list[RetrievedPolicyChunk]:
        self.called_strategy = "hnsw"
        return []

    def search_chunks(self, **kwargs) -> list[RetrievedPolicyChunk]:
        self.called_strategy = "legacy"
        return []

    def search_chunks_by_keywords(self, **kwargs) -> list[RetrievedPolicyChunk]:
        self.keyword_calls += 1
        return []


def test_build_vector_search_strategy_returns_supported_strategies() -> None:
    assert isinstance(build_vector_search_strategy("exact"), ExactVectorSearchStrategy)
    assert isinstance(build_vector_search_strategy("hnsw"), HnswVectorSearchStrategy)


def test_pipeline_uses_exact_vector_strategy_from_settings(monkeypatch) -> None:
    original_strategy = settings.vector_search_strategy
    monkeypatch.setattr(settings, "vector_search_strategy", "exact")
    repository = TrackingRepository()

    try:
        pipeline = HybridRetrievalPipeline(
            repository=repository,
            embedding_service=StubEmbeddingService(),
        )
        result = pipeline.run(
            RetrievalSearchRequest(
                query="示例管理制度适用于哪些范围",
                top_k=3,
            )
        )
    finally:
        monkeypatch.setattr(settings, "vector_search_strategy", original_strategy)

    assert repository.called_strategy == "exact"
    assert result.strategy == "hybrid-vector-keyword/exact"
    vector_trace = next(trace for trace in result.traces if trace.name == "vector_recall")
    assert vector_trace.source == "pgvector_cosine_exact"
    assert vector_trace.details["strategy"] == "exact"


def test_pipeline_uses_hnsw_vector_strategy_from_settings(monkeypatch) -> None:
    original_strategy = settings.vector_search_strategy
    monkeypatch.setattr(settings, "vector_search_strategy", "hnsw")
    repository = TrackingRepository()

    try:
        pipeline = HybridRetrievalPipeline(
            repository=repository,
            embedding_service=StubEmbeddingService(),
        )
        result = pipeline.run(
            RetrievalSearchRequest(
                query="示例管理制度适用于哪些范围",
                top_k=3,
            )
        )
    finally:
        monkeypatch.setattr(settings, "vector_search_strategy", original_strategy)

    assert repository.called_strategy == "hnsw"
    assert result.strategy == "hybrid-vector-keyword/hnsw"
    vector_trace = next(trace for trace in result.traces if trace.name == "vector_recall")
    assert vector_trace.source == "pgvector_hnsw"
    assert vector_trace.details["strategy"] == "hnsw"


def test_pipeline_request_mode_selects_exact_vector_only() -> None:
    repository = TrackingRepository()
    pipeline = HybridRetrievalPipeline(
        repository=repository,
        embedding_service=StubEmbeddingService(),
    )

    result = pipeline.run(
        RetrievalSearchRequest(
            query="绀轰緥绠＄悊鍒跺害閫傜敤浜庡摢浜涜寖鍥?",
            top_k=3,
            retrieval_mode="exact",
        )
    )

    assert repository.called_strategy == "exact"
    assert repository.keyword_calls == 0
    assert result.strategy == "exact-vector/exact"
    assert next(trace for trace in result.traces if trace.name == "keyword_recall").source == (
        "disabled_by_mode"
    )


def test_pipeline_request_mode_selects_hnsw_vector_only() -> None:
    repository = TrackingRepository()
    pipeline = HybridRetrievalPipeline(
        repository=repository,
        embedding_service=StubEmbeddingService(),
    )

    result = pipeline.run(
        RetrievalSearchRequest(
            query="绀轰緥绠＄悊鍒跺害閫傜敤浜庡摢浜涜寖鍥?",
            top_k=3,
            retrieval_mode="hnsw",
        )
    )

    assert repository.called_strategy == "hnsw"
    assert repository.keyword_calls == 0
    assert result.strategy == "hnsw-vector/hnsw"
    vector_trace = next(trace for trace in result.traces if trace.name == "vector_recall")
    assert vector_trace.source == "pgvector_hnsw"
