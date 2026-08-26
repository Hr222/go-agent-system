from __future__ import annotations

from dataclasses import replace

from app.platform.knowledge.retrieval.contracts import RetrievedPolicyChunk
from app.platform.knowledge.retrieval.policies import (
    PolicyRetrievalQueryPolicy,
    RetrievalKeywordPlan,
)


class HeuristicRetrievalReranker:
    """负责当前启发式 rerank 规则，避免 pipeline 混入过多排序细节。"""

    source_name = "heuristic_lexical_alignment"

    def __init__(
        self,
        *,
        query_policy: PolicyRetrievalQueryPolicy,
        base_weight: float = 1.0,
        signal_weight: float = 0.4,
    ) -> None:
        self.query_policy = query_policy
        self.base_weight = base_weight
        self.signal_weight = signal_weight

    def rerank_hits(
        self,
        *,
        query: str,
        keyword_plan: RetrievalKeywordPlan,
        hits: list[RetrievedPolicyChunk],
    ) -> list[RetrievedPolicyChunk]:
        if not hits:
            return []

        reranked_hits: list[RetrievedPolicyChunk] = []
        normalized_query = self.query_policy.normalize_query(query)
        for hit in hits:
            rerank_score, coverage_ratio, rerank_details = self._compute_rerank_signal(
                hit=hit,
                normalized_query=normalized_query,
                keyword_plan=keyword_plan,
            )
            final_score = min(
                1.0,
                max(
                    0.0,
                    hit.score * self.base_weight + rerank_score * self.signal_weight,
                ),
            )
            reranked_hits.append(
                replace(
                    hit,
                    score=round(final_score, 6),
                    score_breakdown={
                        **hit.score_breakdown,
                        "rerank": rerank_score,
                        "coverage": coverage_ratio,
                    },
                    debug_details={
                        **hit.debug_details,
                        **rerank_details,
                    },
                )
            )

        reranked_hits.sort(
            key=lambda item: (
                -item.score,
                -item.score_breakdown.get("rerank", 0.0),
                -item.score_breakdown.get("keyword", 0.0),
                -item.score_breakdown.get("vector", 0.0),
                item.chunk_id,
            )
        )
        return reranked_hits

    def build_trace_details(
        self,
        *,
        query: str,
        keyword_plan: RetrievalKeywordPlan,
        before_hits: list[RetrievedPolicyChunk],
        after_hits: list[RetrievedPolicyChunk],
    ) -> dict[str, str | int | float | bool | None]:
        details: dict[str, str | int | float | bool | None] = {
            "query": query,
            "focus_query": keyword_plan.focus_query or None,
            "formula": (
                f"final={self.base_weight:.2f}*fusion+"
                f"{self.signal_weight:.2f}*rerank"
            ),
        }

        before_rank = {
            hit.chunk_id: index for index, hit in enumerate(before_hits, start=1)
        }
        for index, hit in enumerate(after_hits[:3], start=1):
            matched_keywords = hit.debug_details.get("rerank_matched_keywords") or "-"
            matched_fields = hit.debug_details.get("rerank_matched_fields") or "-"
            rerank_score = hit.score_breakdown.get("rerank", 0.0)
            details[f"sample_hit_{index}"] = (
                f"before_rank={before_rank.get(hit.chunk_id, '-')} "
                f"after_rank={index} "
                f"chunk={hit.chunk_id} "
                f"final={hit.score:.4f} "
                f"rerank={rerank_score:.4f} "
                f"fields={matched_fields} "
                f"keywords={matched_keywords}"
            )

        changed_chunks = [
            str(hit.chunk_id)
            for index, hit in enumerate(after_hits[:5], start=1)
            if before_rank.get(hit.chunk_id) != index
        ]
        details["changed_top5_chunks"] = ", ".join(changed_chunks) or None
        return details

    def _compute_rerank_signal(
        self,
        *,
        hit: RetrievedPolicyChunk,
        normalized_query: str,
        keyword_plan: RetrievalKeywordPlan,
    ) -> tuple[float, float, dict[str, str | int | float | bool | None]]:
        normalized_chunk_text = self.query_policy.normalize_query(hit.chunk_text)
        normalized_policy_name = self.query_policy.normalize_query(hit.policy_name)
        normalized_section_title = self.query_policy.normalize_query(hit.section_title or "")
        normalized_section_path = self.query_policy.normalize_query(hit.section_path or "")

        score = 0.0
        matched_fields: list[str] = []
        matched_keywords: list[str] = []
        matched_anchor_keywords: list[str] = []
        missing_required_keywords: list[str] = []
        term_weight_map = self._build_term_weight_map(keyword_plan)

        def append_field(field_name: str) -> None:
            if field_name not in matched_fields:
                matched_fields.append(field_name)

        def matches_any_field(term: str) -> bool:
            return any(
                term in field_value
                for field_value in (
                    normalized_chunk_text,
                    normalized_section_title,
                    normalized_section_path,
                    normalized_policy_name,
                )
            )

        def add_match(
            term: str,
            *,
            chunk_weight: float,
            section_title_weight: float,
            section_path_weight: float,
            policy_name_weight: float,
        ) -> None:
            nonlocal score
            if not term:
                return

            matched = False
            if term in normalized_chunk_text:
                score += chunk_weight
                append_field("chunk_text")
                matched = True
            if term in normalized_section_title:
                score += section_title_weight
                append_field("section_title")
                matched = True
            if term in normalized_section_path:
                score += section_path_weight
                append_field("section_path")
                matched = True
            if term in normalized_policy_name:
                score += policy_name_weight
                append_field("policy_name")
                matched = True
            if matched and term not in matched_keywords:
                matched_keywords.append(term)

        if normalized_query:
            add_match(
                normalized_query,
                chunk_weight=0.08,
                section_title_weight=0.03,
                section_path_weight=0.02,
                policy_name_weight=0.01,
            )

        if keyword_plan.focus_query:
            add_match(
                keyword_plan.focus_query,
                chunk_weight=0.32,
                section_title_weight=0.12,
                section_path_weight=0.08,
                policy_name_weight=0.02,
            )
            focus_position = normalized_chunk_text.find(keyword_plan.focus_query)
            if 0 <= focus_position <= 24:
                score += 0.08
            for priority_term in self._build_priority_terms(keyword_plan.focus_query):
                if len(priority_term) >= 3:
                    add_match(
                        priority_term,
                        chunk_weight=0.16,
                        section_title_weight=0.08,
                        section_path_weight=0.05,
                        policy_name_weight=0.0,
                    )
                else:
                    add_match(
                        priority_term,
                        chunk_weight=0.10,
                        section_title_weight=0.05,
                        section_path_weight=0.03,
                        policy_name_weight=0.0,
                    )

        for keyword in keyword_plan.anchor_keywords:
            add_match(
                keyword,
                chunk_weight=0.16 if len(keyword) >= 4 else 0.12,
                section_title_weight=0.09 if len(keyword) >= 4 else 0.06,
                section_path_weight=0.06 if len(keyword) >= 4 else 0.04,
                policy_name_weight=0.04 if len(keyword) >= 4 else 0.02,
            )
            if matches_any_field(keyword) and keyword not in matched_anchor_keywords:
                matched_anchor_keywords.append(keyword)

        anchor_keyword_set = set(keyword_plan.anchor_keywords)
        priority_keyword_set = set(keyword_plan.priority_keywords)
        for keyword in keyword_plan.priority_keywords:
            if keyword in anchor_keyword_set:
                continue
            add_match(
                keyword,
                chunk_weight=0.14,
                section_title_weight=0.08,
                section_path_weight=0.05,
                policy_name_weight=0.10,
            )
            if not matches_any_field(keyword) and self._is_required_priority_keyword(keyword):
                missing_required_keywords.append(keyword)

        for keyword in keyword_plan.keywords:
            if keyword in priority_keyword_set:
                continue
            if len(keyword) >= 4:
                add_match(
                    keyword,
                    chunk_weight=0.09,
                    section_title_weight=0.05,
                    section_path_weight=0.035,
                    policy_name_weight=0.01,
                )
            elif len(keyword) == 3:
                add_match(
                    keyword,
                    chunk_weight=0.07,
                    section_title_weight=0.04,
                    section_path_weight=0.03,
                    policy_name_weight=0.008,
                )
            else:
                add_match(
                    keyword,
                    chunk_weight=0.045,
                    section_title_weight=0.025,
                    section_path_weight=0.02,
                    policy_name_weight=0.005,
                )

        if matched_keywords:
            score += min(
                0.18,
                len(matched_keywords) / max(1, min(6, len(keyword_plan.keywords))) * 0.18,
            )

        matched_weight = sum(term_weight_map.get(term, 0.0) for term in matched_keywords)
        total_weight = max(1.0, sum(term_weight_map.values()))
        coverage_ratio = round(min(1.0, matched_weight / total_weight), 6)
        score += min(0.2, coverage_ratio * 0.2)

        anchor_match_ratio = 0.0
        if keyword_plan.anchor_keywords:
            anchor_match_ratio = round(
                len(matched_anchor_keywords) / len(keyword_plan.anchor_keywords),
                6,
            )
            score += min(0.14, anchor_match_ratio * 0.14)

        if missing_required_keywords and not matched_anchor_keywords:
            score -= min(0.12, len(missing_required_keywords) * 0.04)

        rerank_score = round(min(1.0, max(0.0, score)), 6)
        return rerank_score, coverage_ratio, {
            "rerank_matched_fields": ", ".join(matched_fields) or None,
            "rerank_matched_keywords": ", ".join(matched_keywords[:8]) or None,
            "rerank_matched_anchor_keywords": ", ".join(matched_anchor_keywords[:6]) or None,
            "rerank_missing_required_keywords": ", ".join(missing_required_keywords[:6]) or None,
            "rerank_anchor_match_ratio": anchor_match_ratio,
            "rerank_coverage_ratio": coverage_ratio,
        }

    def _build_priority_terms(self, focus_query: str) -> list[str]:
        priority_terms: list[str] = []
        normalized_focus_query = self.query_policy.normalize_query(focus_query)
        for size in (4, 3, 2):
            if len(normalized_focus_query) < size:
                continue
            term = normalized_focus_query[-size:]
            if not self.query_policy.should_keep_keyword(term):
                continue
            if term not in priority_terms:
                priority_terms.append(term)
        return priority_terms

    def _is_required_priority_keyword(self, keyword: str) -> bool:
        return any(char.isdigit() for char in keyword)

    def _build_term_weight_map(
        self,
        keyword_plan: RetrievalKeywordPlan,
    ) -> dict[str, float]:
        weights: dict[str, float] = {}

        if keyword_plan.focus_query:
            weights[keyword_plan.focus_query] = max(
                weights.get(keyword_plan.focus_query, 0.0),
                1.8 if len(keyword_plan.focus_query) >= 4 else 1.2,
            )

        for keyword in keyword_plan.priority_keywords:
            weights[keyword] = max(
                weights.get(keyword, 0.0),
                1.6 if len(keyword) >= 6 else 1.3,
            )

        for keyword in keyword_plan.anchor_keywords:
            weights[keyword] = max(
                weights.get(keyword, 0.0),
                1.8 if len(keyword) >= 4 else 1.2,
            )

        for keyword in keyword_plan.keywords:
            weights[keyword] = max(
                weights.get(keyword, 0.0),
                1.0 if len(keyword) >= 4 else 0.6,
            )

        return weights
