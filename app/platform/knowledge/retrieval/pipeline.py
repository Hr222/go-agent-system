from __future__ import annotations

from app.platform.knowledge.ports.read_port import KnowledgeQuery, KnowledgeRetrievalMode
from app.platform.knowledge.retrieval.contracts import (
    QueryEmbeddingService,
    RetrievalRepository,
    RetrievedPolicyChunk,
)
from app.platform.knowledge.retrieval.fusion import HybridHitFusionService
from app.platform.knowledge.retrieval.models import RetrievalPipelineResult, RetrievalStageTrace
from app.platform.knowledge.retrieval.policies import (
    PolicyRetrievalQueryPolicy,
    RetrievalKeywordPlan,
)
from app.platform.knowledge.retrieval.rerank import HeuristicRetrievalReranker
from app.platform.knowledge.retrieval.vector_search import (
    ExactVectorSearchStrategy,
    HnswVectorSearchStrategy,
    VectorSearchRequest,
    VectorSearchStrategy,
    build_vector_search_strategy,
)
from app.shared.config import settings


class HybridRetrievalPipeline:
    """负责检索主链路编排，只做流程组织，不承载具体融合与重排细节。"""

    pipeline_name = "knowledge-retrieval-v2"
    strategy_name = "hybrid-vector-keyword"

    def __init__(
        self,
        repository: RetrievalRepository,
        embedding_service: QueryEmbeddingService | None = None,
        query_policy: PolicyRetrievalQueryPolicy | None = None,
        fusion_service: HybridHitFusionService | None = None,
        reranker: HeuristicRetrievalReranker | None = None,
        vector_search_strategy: VectorSearchStrategy | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.query_policy = query_policy or PolicyRetrievalQueryPolicy()
        self.fusion_service = fusion_service or HybridHitFusionService()
        self.reranker = reranker or HeuristicRetrievalReranker(
            query_policy=self.query_policy
        )
        self.vector_search_strategy = vector_search_strategy or build_vector_search_strategy(
            settings.vector_search_strategy
        )
        # 保留旧属性名，避免旧测试或调用方直接读取时断裂。
        self.rerank_base_weight = self.reranker.base_weight
        self.rerank_signal_weight = self.reranker.signal_weight

    def run(self, request: KnowledgeQuery) -> RetrievalPipelineResult:
        retrieval_mode = request.retrieval_mode
        vector_search_strategy = self._resolve_vector_search_strategy(retrieval_mode)
        use_hybrid_recall = retrieval_mode == "hybrid"
        # 双路召回时，每一路都多取一些候选，给后续融合和重排留空间。
        per_source_top_k = min(
            settings.retrieval_top_k_max,
            max(request.top_k, request.top_k * 2),
        )
        # 先按查询语义提取更适合关键词召回的核心片段，避免“哪些/多久”之类问句外壳干扰。
        keyword_plan = (
            self.query_policy.build_keyword_plan(request.query)
            if use_hybrid_recall
            else RetrievalKeywordPlan(normalized_query="", focus_query="", keywords=[])
        )
        if self.embedding_service is None:
            raise RuntimeError("知识检索缺少查询向量适配器。")
        query_embedding = self.embedding_service.embed_query(request.query)

        vector_hits = vector_search_strategy.search(
            repository=self.repository,
            request=VectorSearchRequest(
                query_embedding=query_embedding,
                top_k=per_source_top_k,
                policy_category=request.policy_category,
                responsible_department=request.responsible_department,
                document_id=request.document_id,
                include_history=request.include_history,
            ),
        )
        keyword_hits = (
            self.repository.search_chunks_by_keywords(
                focus_query=keyword_plan.focus_query,
                keywords=keyword_plan.keywords,
                priority_keywords=keyword_plan.priority_keywords,
                top_k=per_source_top_k,
                policy_category=request.policy_category,
                responsible_department=request.responsible_department,
                document_id=request.document_id,
                include_history=request.include_history,
            )
            if use_hybrid_recall
            else []
        )
        fused_hits = self._merge_hits(
            vector_hits=vector_hits,
            keyword_hits=keyword_hits,
        )
        reranked_hits = (
            self._rerank_hits(
                query=request.query,
                keyword_plan=keyword_plan,
                hits=fused_hits,
            )
            if use_hybrid_recall
            else fused_hits
        )
        # 阈值过滤放在融合与重排之后执行，避免单路低分但双路一致命中的结果被过早丢掉。
        rescued_hit_count = 0
        filtered_hits: list[RetrievedPolicyChunk] = []
        for item in reranked_hits:
            if item.score >= settings.retrieval_min_score:
                filtered_hits.append(item)
            elif self._passes_evidence_gate(item):
                rescued_hit_count += 1
                filtered_hits.append(item)

            if len(filtered_hits) >= request.top_k:
                break

        traces = [
            RetrievalStageTrace(
                name="query_embedding",
                source="gitee_embedding",
                input_count=1,
                output_count=1,
                details={"dimensions": len(query_embedding)},
            ),
            RetrievalStageTrace(
                name="vector_recall",
                source=vector_search_strategy.source_name,
                input_count=None,
                output_count=len(vector_hits),
                details={
                    "strategy": vector_search_strategy.strategy_name,
                    "top_k": per_source_top_k,
                    "include_history": request.include_history,
                    "document_filter": request.document_id,
                    "policy_category_filter": request.policy_category,
                    "department_filter": request.responsible_department,
                },
            ),
            RetrievalStageTrace(
                name="keyword_recall",
                source="like_keyword_match" if use_hybrid_recall else "disabled_by_mode",
                input_count=len(keyword_plan.keywords) if use_hybrid_recall else 0,
                output_count=len(keyword_hits),
                details=(
                    self._build_keyword_recall_trace_details(
                        per_source_top_k=per_source_top_k,
                        keyword_plan=keyword_plan,
                        keyword_hits=keyword_hits,
                    )
                    if use_hybrid_recall
                    else {"mode": retrieval_mode}
                ),
            ),
            RetrievalStageTrace(
                name="result_fusion",
                source=self.fusion_service.source_name,
                input_count=len(vector_hits) + len(keyword_hits),
                output_count=len(fused_hits),
                details={
                    "duplicate_chunk_count": (
                        len(vector_hits) + len(keyword_hits) - len(fused_hits)
                    ),
                },
            ),
            RetrievalStageTrace(
                name="rerank",
                source=self.reranker.source_name if use_hybrid_recall else "disabled_by_mode",
                input_count=len(fused_hits),
                output_count=len(reranked_hits),
                details=(
                    self._build_rerank_trace_details(
                        query=request.query,
                        keyword_plan=keyword_plan,
                        before_hits=fused_hits,
                        after_hits=reranked_hits,
                    )
                    if use_hybrid_recall
                    else {"mode": retrieval_mode}
                ),
            ),
            RetrievalStageTrace(
                name="score_filter",
                source="min_score_threshold",
                input_count=len(reranked_hits),
                output_count=len(filtered_hits),
                details={
                    "min_score": settings.retrieval_min_score,
                    "evidence_min_coverage": settings.retrieval_evidence_min_coverage,
                    "evidence_rescue_margin": settings.retrieval_evidence_rescue_margin,
                    "rescued_hit_count": rescued_hit_count,
                },
            ),
        ]

        return RetrievalPipelineResult(
            hits=filtered_hits,
            pipeline=self.pipeline_name,
            strategy=(
                f"{self.strategy_name}/{vector_search_strategy.strategy_name}"
                if use_hybrid_recall
                else f"{retrieval_mode}-vector/{vector_search_strategy.strategy_name}"
            ),
            min_score=settings.retrieval_min_score,
            traces=traces,
        )

    def _resolve_vector_search_strategy(
        self,
        retrieval_mode: KnowledgeRetrievalMode,
    ) -> VectorSearchStrategy:
        if retrieval_mode == "exact":
            return ExactVectorSearchStrategy()
        if retrieval_mode == "hnsw":
            return HnswVectorSearchStrategy()
        if retrieval_mode == "hybrid":
            return self.vector_search_strategy
        raise ValueError(f"不支持的检索模式：{retrieval_mode}")

    def _build_keyword_recall_trace_details(
        self,
        *,
        per_source_top_k: int,
        keyword_plan: RetrievalKeywordPlan,
        keyword_hits: list[RetrievedPolicyChunk],
    ) -> dict[str, str | int | float | bool | None]:
        details: dict[str, str | int | float | bool | None] = {
            "top_k": per_source_top_k,
            "focus_query": keyword_plan.focus_query or None,
            "keyword_count": len(keyword_plan.keywords),
            "priority_keyword_count": len(keyword_plan.priority_keywords),
            "anchor_keyword_count": len(keyword_plan.anchor_keywords),
            "keywords_preview": ", ".join(keyword_plan.keywords[:6]) or None,
            "priority_keywords_preview": ", ".join(keyword_plan.priority_keywords[:6]) or None,
            "anchor_keywords_preview": ", ".join(keyword_plan.anchor_keywords[:6]) or None,
        }

        # MVP 阶段先把前三条关键词命中的原因压缩成字符串，方便人工观察效果。
        for index, hit in enumerate(keyword_hits[:3], start=1):
            matched_fields = hit.debug_details.get("matched_fields") or "-"
            matched_keywords = hit.debug_details.get("matched_keywords") or "-"
            score_terms = hit.debug_details.get("keyword_score_terms") or "-"
            details[f"sample_hit_{index}"] = (
                f"chunk={hit.chunk_id} "
                f"fields={matched_fields} "
                f"keywords={matched_keywords} "
                f"terms={score_terms}"
            )

        return details

    def _build_rerank_trace_details(
        self,
        *,
        query: str,
        keyword_plan: RetrievalKeywordPlan,
        before_hits: list[RetrievedPolicyChunk],
        after_hits: list[RetrievedPolicyChunk],
    ) -> dict[str, str | int | float | bool | None]:
        return self.reranker.build_trace_details(
            query=query,
            keyword_plan=keyword_plan,
            before_hits=before_hits,
            after_hits=after_hits,
        )

    def _merge_hits(
        self,
        *,
        vector_hits: list[RetrievedPolicyChunk],
        keyword_hits: list[RetrievedPolicyChunk],
    ) -> list[RetrievedPolicyChunk]:
        return self.fusion_service.merge_hits(
            vector_hits=vector_hits,
            keyword_hits=keyword_hits,
        )

    def _rerank_hits(
        self,
        *,
        query: str,
        keyword_plan: RetrievalKeywordPlan,
        hits: list[RetrievedPolicyChunk],
    ) -> list[RetrievedPolicyChunk]:
        return self.reranker.rerank_hits(
            query=query,
            keyword_plan=keyword_plan,
            hits=hits,
        )

    def _passes_evidence_gate(self, hit: RetrievedPolicyChunk) -> bool:
        if hit.retrieval_source == "vector":
            return False

        score_floor = settings.retrieval_min_score - settings.retrieval_evidence_rescue_margin
        if hit.score < score_floor:
            return False

        coverage_ratio = hit.score_breakdown.get("coverage", 0.0)
        rerank_score = hit.score_breakdown.get("rerank", 0.0)
        keyword_score = hit.score_breakdown.get("keyword", 0.0)

        return (
            coverage_ratio >= settings.retrieval_evidence_min_coverage
            and max(rerank_score, keyword_score) >= 0.12
        )


# 当前仍保留旧别名，避免既有调用误以为这里是“只做 exact 向量检索”的另一套实现。
ExactVectorRetrievalPipeline = HybridRetrievalPipeline
