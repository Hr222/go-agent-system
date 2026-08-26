from __future__ import annotations

from app.business.online.domain.decision_result import DecisionResult, DecisionReviewCommand
from app.interfaces.http.schemas.policy_decision import (
    PolicyDecisionDataAcquisitionDebug,
    PolicyDecisionDataFieldTrace,
    PolicyDecisionDebugInfo,
    PolicyDecisionRequest,
    PolicyDecisionRequirementStatus,
    PolicyDecisionResponse,
)
from app.interfaces.http.schemas.retrieval import (
    AnswerCitation,
    RetrievalDebugInfo,
    RetrievalStageDebug,
)


def decision_command(
    request: PolicyDecisionRequest,
    *,
    scenario_code: str | None = None,
) -> DecisionReviewCommand:
    return DecisionReviewCommand(
        submitted_materials=tuple(request.submitted_materials),
        top_k=request.top_k,
        document_id=request.document_id,
        include_history=request.include_history,
        submitted_materials_provided="submitted_materials" in request.model_fields_set,
        scenario_code=scenario_code,
    )


def decision_response(result: DecisionResult) -> PolicyDecisionResponse:
    return PolicyDecisionResponse(
        scenario_code=result.scenario_code,
        scenario_name=result.scenario_name,
        decision=result.decision,
        reasoning=list(result.reasoning),
        citations=[
            AnswerCitation(
                ref_no=item.ref_no,
                document_id=item.document_id,
                version_id=item.version_id,
                chunk_id=item.chunk_id,
                policy_name=item.policy_name,
                section_title=item.section_title,
                page_no=item.page_no,
                quote=item.quote,
                source_path=item.source_path,
                file_name=item.file_name,
            )
            for item in result.citations
        ],
        used_fields=list(result.used_fields),
        missing_input_fields=list(result.missing_input_fields),
        missing_fields=list(result.missing_fields),
        requirement_statuses=[
            PolicyDecisionRequirementStatus(
                field_key=item.field_key,
                label=item.label,
                rule_matched=item.rule_matched,
                submitted=item.submitted,
                matched_rule_keywords=list(item.matched_rule_keywords),
                matched_submission_items=list(item.matched_submission_items),
                matched_components=list(item.matched_components),
                missing_components=list(item.missing_components),
            )
            for item in result.requirement_statuses
        ],
        debug=PolicyDecisionDebugInfo(
            retrieval_query=result.debug.retrieval_query,
            policy_category=result.debug.policy_category,
            provider=result.debug.provider,
            rule_hit_count=result.debug.rule_hit_count,
            matched_rule_requirement_count=result.debug.matched_rule_requirement_count,
            submitted_material_count=result.debug.submitted_material_count,
            data_acquisition=PolicyDecisionDataAcquisitionDebug(
                provider=result.debug.data_acquisition.provider,
                provided_input_fields=list(result.debug.data_acquisition.provided_input_fields),
                missing_input_fields=list(result.debug.data_acquisition.missing_input_fields),
                field_traces=[
                    PolicyDecisionDataFieldTrace(
                        field_key=item.field_key,
                        label=item.label,
                        source=item.source,
                        provided=item.provided,
                        value_count=item.value_count,
                    )
                    for item in result.debug.data_acquisition.field_traces
                ],
            ),
            retrieval=RetrievalDebugInfo(
                pipeline=result.debug.retrieval_pipeline,
                strategy=result.debug.retrieval_strategy,
                min_score=result.debug.retrieval_min_score,
                stages=[
                    RetrievalStageDebug(
                        name=item.name,
                        source=item.source,
                        input_count=item.input_count,
                        output_count=item.output_count,
                        details=item.details,
                    )
                    for item in result.debug.retrieval
                ],
            ),
        ),
    )
