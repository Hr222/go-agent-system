from __future__ import annotations

from app.platform.knowledge.retrieval import HybridHitFusionService, HybridRetrievalPipeline
from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk


def _hit(
    *,
    chunk_id: int,
    score: float,
    retrieval_source: str,
    vector_score: float = 0.0,
    keyword_score: float = 0.0,
) -> RetrievedPolicyChunk:
    score_breakdown: dict[str, float] = {}
    if vector_score > 0.0:
        score_breakdown["vector"] = vector_score
    if keyword_score > 0.0:
        score_breakdown["keyword"] = keyword_score

    return RetrievedPolicyChunk(
        document_id=1,
        version_id=1,
        chunk_id=chunk_id,
        policy_name="人事管理制度",
        policy_category="人事制度",
        responsible_department="人力资源部",
        version_label="2025",
        section_title="第二条",
        section_path="总则 / 第二条",
        page_no=1,
        chunk_text="本制度适用于公司全体员工。",
        score=score,
        retrieval_source=retrieval_source,
        score_breakdown=score_breakdown,
        debug_details={},
    )


def test_fusion_service_merges_duplicate_hits_and_keeps_breakdown() -> None:
    fusion_service = HybridHitFusionService()

    merged_hits = fusion_service.merge_hits(
        vector_hits=[
            _hit(
                chunk_id=10,
                score=0.78,
                retrieval_source="vector",
                vector_score=0.78,
            )
        ],
        keyword_hits=[
            _hit(
                chunk_id=10,
                score=0.82,
                retrieval_source="keyword",
                keyword_score=0.82,
            ),
            _hit(
                chunk_id=20,
                score=0.65,
                retrieval_source="keyword",
                keyword_score=0.65,
            ),
        ],
    )

    assert [item.chunk_id for item in merged_hits] == [10, 20]
    assert merged_hits[0].retrieval_source == "hybrid"
    assert merged_hits[0].score_breakdown == {
        "vector": 0.78,
        "keyword": 0.82,
    }


def test_retrieval_pipeline_is_exposed_from_retrieval_package() -> None:
    assert HybridRetrievalPipeline.__name__ == "HybridRetrievalPipeline"
