from __future__ import annotations

from dataclasses import replace

from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk


class HybridHitFusionService:
    """负责双路召回结果融合，避免 pipeline 本身承担具体融合细节。"""

    source_name = "chunk_id_dedup"

    def merge_hits(
        self,
        *,
        vector_hits: list[RetrievedPolicyChunk],
        keyword_hits: list[RetrievedPolicyChunk],
    ) -> list[RetrievedPolicyChunk]:
        # 以 chunk_id 作为融合主键，保证同一切块不会重复展示。
        merged_by_chunk: dict[int, RetrievedPolicyChunk] = {}

        for hit in vector_hits + keyword_hits:
            existing = merged_by_chunk.get(hit.chunk_id)
            if existing is None:
                merged_by_chunk[hit.chunk_id] = replace(
                    hit,
                    score_breakdown=dict(hit.score_breakdown),
                )
                continue

            # 命中同一切块时，分别保留各路最高分，再重算融合分。
            vector_score = max(
                existing.score_breakdown.get("vector", 0.0),
                hit.score_breakdown.get("vector", 0.0),
            )
            keyword_score = max(
                existing.score_breakdown.get("keyword", 0.0),
                hit.score_breakdown.get("keyword", 0.0),
            )
            existing.score_breakdown = {
                key: round(value, 6)
                for key, value in {
                    "vector": vector_score,
                    "keyword": keyword_score,
                }.items()
                if value > 0.0
            }
            existing.score = self._fuse_score(
                vector_score=vector_score,
                keyword_score=keyword_score,
            )
            existing.retrieval_source = self._resolve_retrieval_source(
                vector_score=vector_score,
                keyword_score=keyword_score,
            )

        ranked_hits = list(merged_by_chunk.values())
        # 先看融合分，再用关键词分和向量分做稳定排序。
        ranked_hits.sort(
            key=lambda item: (
                -item.score,
                -item.score_breakdown.get("keyword", 0.0),
                -item.score_breakdown.get("vector", 0.0),
                item.chunk_id,
            )
        )
        return ranked_hits

    def _fuse_score(self, *, vector_score: float, keyword_score: float) -> float:
        # 第一版融合规则保持可解释：
        # 双路都命中时，在主路高分基础上叠加辅路加成；单路命中时直接取该路分数。
        if vector_score > 0.0 and keyword_score > 0.0:
            return round(
                min(
                    1.0,
                    max(vector_score, keyword_score)
                    + min(vector_score, keyword_score) * 0.25,
                ),
                6,
            )
        return round(max(vector_score, keyword_score), 6)

    def _resolve_retrieval_source(
        self,
        *,
        vector_score: float,
        keyword_score: float,
    ) -> str:
        if vector_score > 0.0 and keyword_score > 0.0:
            return "hybrid"
        if keyword_score > 0.0:
            return "keyword"
        return "vector"
