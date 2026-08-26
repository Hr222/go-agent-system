from __future__ import annotations

from collections.abc import Iterable

from app.business.online.application.rule_retrieval.contracts import (
    RetrievalSearcher,
    RuleRetrievalRequest,
)
from app.business.online.application.rule_retrieval.models import RulePack
from app.business.online.contracts import AnswerCitationResult
from app.business.online.domain.checklist import (
    ChecklistScenarioDefinition,
    ChecklistScenarioRegistry,
    RuleDrivenChecklistPolicy,
)
from app.platform.knowledge.ports.read_port import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeQueryTrace,
    KnowledgeSearchHit,
)
from app.shared.config import settings


class PolicyRuleRetrievalService:
    """面向业务场景消费检索能力，并输出统一规则包。"""

    def __init__(
        self,
        retrieval_service: RetrievalSearcher,
        *,
        scenario_registry: ChecklistScenarioRegistry,
        checklist_policy: RuleDrivenChecklistPolicy | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.scenario_registry = scenario_registry
        self.checklist_policy = checklist_policy or RuleDrivenChecklistPolicy()

    def retrieve_rule_pack(self, request: RuleRetrievalRequest) -> RulePack:
        scenario = self.scenario_registry.get(request.scenario_code)

        # 先由场景定义提供检索语义，再调用 Knowledge 层获取原始规则证据。
        raw_result = self.retrieval_service.search(
            self._build_search_request(request=request, scenario=scenario)
        )

        # 统一不同检索实现的返回结构，后续逻辑只处理 KnowledgeQueryResult。
        search_result = self._normalize_search_result(
            raw_result,
            request=request,
            scenario=scenario,
        )

        # Checklist Policy 只负责把命中的规则文本映射为场景要求，不负责执行检索。
        checklist_rule_pack = self.checklist_policy.build_rule_pack(
            scenario=scenario,
            rule_texts=[hit.chunk_text for hit in search_result.hits],
        )

        # 规则命中数量不足时，保留统一原因，供决策层返回“证据不足”。
        insufficient_reason = self._build_insufficient_reason(
            hits=search_result.hits,
            matched_requirement_count=checklist_rule_pack.matched_requirement_count,
            min_rule_match_count=scenario.min_rule_match_count,
        )
        return RulePack(
            scenario=scenario,
            original_query=scenario.retrieval_query,
            matched_rule_chunks=search_result.hits,
            citations=self._build_citations(search_result),
            retrieval_debug=search_result.traces,
            retrieval_pipeline=search_result.pipeline,
            retrieval_strategy=search_result.strategy,
            retrieval_min_score=search_result.min_score,
            matched_requirement_count=checklist_rule_pack.matched_requirement_count,
            is_sufficient=checklist_rule_pack.is_sufficient,
            insufficient_reason=insufficient_reason,
            checklist_rule_pack=checklist_rule_pack,
        )

    def _build_search_request(
        self,
        *,
        request: RuleRetrievalRequest,
        scenario: ChecklistScenarioDefinition,
    ) -> KnowledgeQuery:
        """把场景定义转换为 Knowledge Query，不在这里拼接具体数据库条件。"""
        return KnowledgeQuery(
            query=scenario.retrieval_query,
            top_k=request.top_k,
            policy_category=scenario.policy_category,
            document_id=request.document_id,
            include_history=request.include_history,
        )

    def _build_citations(
        self,
        search_result: KnowledgeQueryResult,
    ) -> tuple[AnswerCitationResult, ...]:
        """把检索命中转换为可回溯的文档、章节、页码和原文引用。"""
        return tuple(
            AnswerCitationResult(
                ref_no=index,
                document_id=hit.document_id,
                version_id=hit.version_id,
                chunk_id=hit.chunk_id,
                policy_name=hit.policy_name,
                section_title=hit.section_title,
                page_no=hit.page_no,
                quote=hit.chunk_text[: settings.rag_max_context_chars_per_chunk],
                source_path=hit.source_path,
                file_name=hit.file_name,
            )
            for index, hit in enumerate(search_result.hits[: settings.rag_answer_top_k], start=1)
        )

    def _build_insufficient_reason(
        self,
        *,
        hits: Iterable[KnowledgeSearchHit],
        matched_requirement_count: int,
        min_rule_match_count: int,
    ) -> str | None:
        """统一判断没有命中规则或规则清单不完整的情况。"""
        hit_list = list(hits)
        if not hit_list:
            return "当前未检索到可用于该场景判断的规则片段。"
        if matched_requirement_count < min_rule_match_count:
            return (
                "当前命中的规则片段不足以稳定提取完整规则清单，"
                f"仅识别出 {matched_requirement_count} 项要求，"
                f"低于最小阈值 {min_rule_match_count}。"
            )
        return None

    def _normalize_search_result(
        self,
        result: object,
        *,
        request: RuleRetrievalRequest,
        scenario: ChecklistScenarioDefinition,
    ) -> KnowledgeQueryResult:
        """兼容旧返回对象和标准查询结果，避免兼容逻辑扩散到决策流程。"""
        if isinstance(result, KnowledgeQueryResult):
            return result

        raw_hits = tuple(getattr(result, "hits", ()))
        hits = tuple(
            KnowledgeSearchHit(
                document_id=hit.document_id,
                version_id=hit.version_id,
                chunk_id=hit.chunk_id,
                policy_name=hit.policy_name,
                policy_category=hit.policy_category,
                responsible_department=hit.responsible_department,
                version_label=hit.version_label,
                source_path=getattr(hit, "source_path", None),
                file_name=getattr(hit, "file_name", None),
                section_title=hit.section_title,
                section_path=getattr(hit, "section_path", None),
                page_no=hit.page_no,
                chunk_text=hit.chunk_text,
                score=hit.score,
                rank=getattr(hit, "rank", index),
                retrieval_source=hit.retrieval_source,
                score_breakdown=dict(getattr(hit, "score_breakdown", {})),
            )
            for index, hit in enumerate(raw_hits, start=1)
        )
        debug = getattr(result, "debug", None)
        traces = tuple(
            KnowledgeQueryTrace(
                name=item.name,
                source=getattr(item, "source", None),
                input_count=getattr(item, "input_count", None),
                output_count=getattr(item, "output_count", None),
                details=dict(getattr(item, "details", {})),
            )
            for item in getattr(debug, "stages", ())
        )
        return KnowledgeQueryResult(
            query=getattr(result, "query", scenario.retrieval_query),
            top_k=getattr(result, "top_k", request.top_k),
            policy_category=scenario.policy_category,
            responsible_department=None,
            document_id=request.document_id,
            include_history=request.include_history,
            hits=hits,
            pipeline=getattr(debug, "pipeline", "unknown"),
            strategy=getattr(debug, "strategy", "unknown"),
            min_score=float(getattr(debug, "min_score", 0.0)),
            traces=traces,
        )
