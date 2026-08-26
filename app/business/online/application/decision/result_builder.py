from __future__ import annotations

from app.business.online.application.data_acquisition.models import ChecklistDataPack
from app.business.online.contracts import AnswerCitationResult
from app.business.online.domain.checklist import (
    ChecklistEvaluationResult,
    ChecklistRulePack,
    ChecklistScenarioDefinition,
)
from app.business.online.domain.decision_result import (
    DataAcquisitionDebugResult,
    DataFieldTraceResult,
    DecisionDebugResult,
    DecisionResult,
    DecisionRetrievalTrace,
    RequirementStatusResult,
)
from app.platform.knowledge.ports.read_port import KnowledgeQueryResult, KnowledgeQueryTrace
from app.shared.config import settings


class DecisionResultBuilder:
    """将规则评估结果组装为在线应用层内部结果。"""

    def __init__(self, *, scenario: ChecklistScenarioDefinition) -> None:
        self.scenario = scenario

    def build_requirement_statuses_from_rule_pack(
        self,
        rule_pack: ChecklistRulePack,
    ) -> tuple[RequirementStatusResult, ...]:
        return tuple(
            RequirementStatusResult(
                field_key=item.definition.field_key,
                label=item.definition.label,
                rule_matched=item.rule_matched,
                submitted=False,
                matched_rule_keywords=tuple(item.matched_rule_keywords),
            )
            for item in rule_pack.requirements
        )

    def build_requirement_statuses_from_evaluation(
        self,
        evaluation: ChecklistEvaluationResult,
    ) -> tuple[RequirementStatusResult, ...]:
        return tuple(
            RequirementStatusResult(
                field_key=item.evidence.definition.field_key,
                label=item.evidence.definition.label,
                rule_matched=item.evidence.rule_matched,
                submitted=item.submitted,
                matched_rule_keywords=tuple(item.evidence.matched_rule_keywords),
                matched_submission_items=tuple(item.matched_submission_items),
                matched_components=tuple(item.matched_components),
                missing_components=tuple(item.missing_components),
            )
            for item in evaluation.decisions
        )

    def build_citations(
        self,
        search_result: KnowledgeQueryResult,
    ) -> tuple[AnswerCitationResult, ...]:
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

    def build_debug_info(
        self,
        *,
        retrieval_debug: tuple[KnowledgeQueryTrace, ...],
        retrieval_pipeline: str,
        retrieval_strategy: str,
        retrieval_min_score: float,
        rule_hit_count: int,
        rule_match_count: int,
        data_pack: ChecklistDataPack,
    ) -> DecisionDebugResult:
        return DecisionDebugResult(
            retrieval_query=self.scenario.retrieval_query,
            policy_category=self.scenario.policy_category,
            provider=data_pack.provider_name,
            rule_hit_count=rule_hit_count,
            matched_rule_requirement_count=rule_match_count,
            submitted_material_count=len(data_pack.submitted_materials),
            data_acquisition=DataAcquisitionDebugResult(
                provider=data_pack.provider_name,
                provided_input_fields=tuple(data_pack.provided_input_fields),
                missing_input_fields=tuple(data_pack.missing_input_fields),
                field_traces=tuple(
                    DataFieldTraceResult(
                        field_key=item.field_key,
                        label=item.label,
                        source=item.source,
                        provided=item.provided,
                        value_count=item.value_count,
                    )
                    for item in data_pack.field_traces
                ),
            ),
            retrieval_pipeline=retrieval_pipeline,
            retrieval_strategy=retrieval_strategy,
            retrieval_min_score=retrieval_min_score,
            retrieval=tuple(
                DecisionRetrievalTrace(
                    name=item.name,
                    source=item.source,
                    input_count=item.input_count,
                    output_count=item.output_count,
                    details=dict(item.details),
                )
                for item in retrieval_debug
            ),
        )

    def build_reasoning(
        self,
        *,
        matched_requirement_count: int,
        submitted_value_count: int,
        missing_fields: list[str],
    ) -> list[str]:
        """根据通用规则、输入和缺失项信息生成可消费的判断依据。"""
        reasoning = [
            f"已从命中的规则片段中识别出 {matched_requirement_count} 项校验要求。",
            f"本次收到 {submitted_value_count} 项业务输入。",
        ]
        reasoning.append(
            f"仍缺少 {len(missing_fields)} 项必需要求。"
            if missing_fields
            else "当前业务输入已覆盖规则要求。"
        )
        return reasoning

    def build_rule_insufficient_reasoning(self, insufficient_reason: str | None) -> list[str]:
        """生成规则证据不足时的统一说明。"""
        reasoning = [
            "当前命中的规则证据不足以稳定提取完整的业务要求。",
            "该场景应先确认规则依据，再继续进行字段校验。",
        ]
        if insufficient_reason:
            reasoning.insert(1, insufficient_reason)
        return reasoning

    def build_data_insufficient_reasoning(self, insufficient_reason: str | None) -> list[str]:
        """生成业务输入不足时的统一说明。"""
        reasoning = ["当前业务输入不足，暂时无法完成稳定校验。"]
        if insufficient_reason:
            reasoning.append(insufficient_reason)
        reasoning.append("请先补齐必要输入字段，再继续执行规则驱动校验。")
        return reasoning

    def build_response(
        self,
        *,
        decision: str,
        reasoning: list[str],
        citations: tuple[AnswerCitationResult, ...],
        used_fields: tuple[str, ...],
        missing_input_fields: tuple[str, ...],
        missing_fields: tuple[str, ...],
        requirement_statuses: tuple[RequirementStatusResult, ...],
        debug: DecisionDebugResult,
    ) -> DecisionResult:
        # 决策值由领域服务限制为 pass / fail / insufficient_evidence，
        # 这里仅将字符串结果装配到领域结果对象。
        return DecisionResult(
            scenario_code=self.scenario.scenario_code,
            scenario_name=self.scenario.scenario_name,
            decision=decision,  # type: ignore[arg-type]
            reasoning=tuple(reasoning),
            citations=citations,
            used_fields=used_fields,
            missing_input_fields=missing_input_fields,
            missing_fields=missing_fields,
            requirement_statuses=requirement_statuses,
            debug=debug,
        )


# 保留旧名称，避免已有应用层导入因结果 builder 通用化而中断。
PolicyDecisionResultBuilder = DecisionResultBuilder
