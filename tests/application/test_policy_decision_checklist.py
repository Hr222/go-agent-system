from __future__ import annotations

from app.business.online.application.decision import RuleDrivenChecklistDecisionService
from app.business.online.domain.checklist import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
    ChecklistRequirementComponent,
    ChecklistRequirementDefinition,
    ChecklistScenarioDefinition,
    ChecklistScenarioRegistry,
)
from app.business.online.domain.decision_result import DecisionReviewCommand
from app.interfaces.http.schemas import (
    RetrievalDebugInfo,
    RetrievalFilters,
    RetrievalHit,
    RetrievalSearchResponse,
    RetrievalStageDebug,
)

RULE_CHUNK_TEXT = (
    "第十条 评估、拍卖机构自愿参与人民法院委托工作的，应在指定时间到人民法院申请登记，"
    "提交相关资料。申请参与委托评估（审计）的机构应提交如下审验资料：\n"
    "(1)申请书、登记表及机构简介；\n"
    "(2)经年检合格的企业法人营业执照副本和税务登记证副本；\n"
    "(3)经年检合格的机构资质、资格证书副本；\n"
    "(4)机构评估（审计）人员名单及其相关资质、机构营业场所证明资料；\n"
    "(5)资格证书副本；\n"
    "(6)注资证明及资产明细表；\n"
    "(7)税务机关出具的纳税证明；\n"
    "(8)法院指定提交的其他资料。"
)


class FakeRetrievalService:
    """用固定命中结果替代真实检索，便于稳定覆盖规则判定路径。"""

    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    def search(self, request):  # noqa: ANN001
        return RetrievalSearchResponse(
            query=request.query,
            top_k=request.top_k,
            filters=RetrievalFilters(
                policy_category=request.policy_category,
                responsible_department=request.responsible_department,
                document_id=request.document_id,
                include_history=request.include_history,
            ),
            hits=self.hits,
            debug=RetrievalDebugInfo(
                pipeline="test-pipeline",
                strategy="test-strategy",
                min_score=0.45,
                stages=[
                    RetrievalStageDebug(
                        name="keyword_recall",
                        source="fake",
                        input_count=1,
                        output_count=len(self.hits),
                    )
                ],
            ),
        )


def _make_hit(chunk_text: str) -> RetrievalHit:
    """构造最小可用的制度命中片段。"""
    return RetrievalHit(
        document_id=101,
        version_id=201,
        chunk_id=301,
        policy_name="广东省高级人民法院关于委托评估拍卖工作的若干规定",
        policy_category="收费标准",
        responsible_department=None,
        version_label="现行",
        section_title="第十条",
        section_path="第十条",
        page_no=1,
        chunk_text=chunk_text,
        score=1.0,
        rank=1,
        retrieval_source="hybrid",
        score_breakdown={"keyword": 1.0},
    )


def _scenario_registry() -> ChecklistScenarioRegistry:
    """为测试显式组装当前场景，避免依赖生产环境全局注册表。"""
    return ChecklistScenarioRegistry(definitions=(COURT_EVALUATION_MATERIALS_SCENARIO,))


def test_rule_driven_checklist_reports_missing_materials() -> None:
    service = RuleDrivenChecklistDecisionService(
        FakeRetrievalService([_make_hit(RULE_CHUNK_TEXT)]),
        scenario_registry=_scenario_registry(),
    )

    response = service.review(
        DecisionReviewCommand(
            submitted_materials=(
                "申请书",
                "机构简介",
                "营业执照副本",
                "税务登记证副本",
                "机构资质证书副本",
                "评估人员名单",
                "相关资质说明",
                "营业场所证明",
                "纳税证明",
            )
        )
    )

    assert response.decision == "fail"
    assert response.missing_input_fields == ()
    assert "资格证书副本" in response.missing_fields
    assert "注资证明及资产明细表" in response.missing_fields
    assert "法院指定提交的其他资料" in response.missing_fields
    assert response.debug.matched_rule_requirement_count == 8
    assert response.debug.data_acquisition.provider == "inline_submitted_materials"


def test_rule_driven_checklist_passes_when_all_materials_exist() -> None:
    service = RuleDrivenChecklistDecisionService(
        FakeRetrievalService([_make_hit(RULE_CHUNK_TEXT)]),
        scenario_registry=_scenario_registry(),
    )

    response = service.review(
        DecisionReviewCommand(
            submitted_materials=(
                "申请书",
                "机构简介",
                "企业法人营业执照副本",
                "税务登记证副本",
                "机构资质证书副本",
                "评估人员名单",
                "相关资质",
                "机构营业场所证明资料",
                "资格证书副本",
                "注资证明",
                "资产明细表",
                "纳税证明",
                "法院指定资料",
            )
        )
    )

    assert response.decision == "pass"
    assert response.missing_input_fields == ()
    assert response.missing_fields == ()
    assert len(response.used_fields) == 8


def test_rule_driven_checklist_returns_insufficient_evidence_for_partial_rule_text() -> None:
    service = RuleDrivenChecklistDecisionService(
        FakeRetrievalService([_make_hit("申请参与委托评估的机构应提交资料，具体要求以法院通知为准。")]),
        scenario_registry=_scenario_registry(),
    )

    response = service.review(
        DecisionReviewCommand(submitted_materials=("申请书", "营业执照副本"))
    )

    assert response.decision == "insufficient_evidence"
    assert response.used_fields == ()
    assert response.missing_input_fields == ()
    assert response.missing_fields == ()
    assert response.debug.matched_rule_requirement_count < 8


def test_rule_driven_checklist_returns_insufficient_evidence_for_missing_business_input() -> None:
    service = RuleDrivenChecklistDecisionService(
        FakeRetrievalService([_make_hit(RULE_CHUNK_TEXT)]),
        scenario_registry=_scenario_registry(),
    )

    response = service.review(DecisionReviewCommand(submitted_materials_provided=False))

    assert response.decision == "insufficient_evidence"
    assert response.used_fields == ()
    assert response.missing_input_fields == ("已提交材料列表",)
    assert response.missing_fields == ()
    assert response.debug.data_acquisition.missing_input_fields == ("已提交材料列表",)


def test_rule_driven_checklist_reuses_the_same_chain_for_another_registered_scenario() -> None:
    second_scenario = ChecklistScenarioDefinition(
        scenario_code="company-registration-review",
        scenario_name="企业登记材料核验",
        retrieval_query="企业登记需要提交哪些材料",
        policy_category="企业登记",
        min_rule_match_count=1,
        input_field_key="registration_materials",
        input_field_label="已提交登记材料",
        requirements=(
            ChecklistRequirementDefinition(
                field_key="registration_certificate",
                label="登记证明",
                components=(
                    ChecklistRequirementComponent(
                        label="登记证明",
                        aliases=("登记证明",),
                    ),
                ),
                evidence_keywords=("登记证明",),
            ),
        ),
    )
    scenario_registry = ChecklistScenarioRegistry(
        definitions=(COURT_EVALUATION_MATERIALS_SCENARIO, second_scenario)
    )
    service = RuleDrivenChecklistDecisionService(
        FakeRetrievalService([_make_hit("企业登记需要提交登记证明。")]),
        scenario_registry=scenario_registry,
    )

    response = service.review(
        DecisionReviewCommand(
            scenario_code="company-registration-review",
            submitted_materials=("登记证明",),
        )
    )

    assert response.scenario_code == "company-registration-review"
    assert response.scenario_name == "企业登记材料核验"
    assert response.decision == "pass"
    assert response.debug.retrieval_query == "企业登记需要提交哪些材料"
    assert response.requirement_statuses[0].field_key == "registration_certificate"
    assert response.debug.data_acquisition.field_traces[0].field_key == "registration_materials"
    assert response.debug.data_acquisition.field_traces[0].label == "已提交登记材料"


def test_scenario_registry_accepts_arbitrary_registered_scenario() -> None:
    definition = ChecklistScenarioDefinition(
        scenario_code="custom-review",
        scenario_name="自定义核验场景",
        retrieval_query="自定义核验需要哪些资料",
        policy_category=None,
        requirements=(),
    )
    registry = ChecklistScenarioRegistry(
        definitions=(definition,),
        default_scenario_code=definition.scenario_code,
    )

    assert registry.get("custom-review") is definition
    assert registry.default() is definition
    assert registry.list_all() == (definition,)
