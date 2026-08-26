from __future__ import annotations

from fastapi.testclient import TestClient

from app.business.online.application.policy_decision import PolicyDecisionApplicationService
from app.business.online.domain.citation import AnswerCitationResult
from app.business.online.domain.decision_result import (
    DataAcquisitionDebugResult,
    DataFieldTraceResult,
    DecisionDebugResult,
    DecisionResult,
    DecisionRetrievalTrace,
    RequirementStatusResult,
)
from app.interfaces.http.dependencies import get_policy_decision_application_service
from app.main import create_app
from app.shared.exceptions import KnowledgeBaseSchemaUnavailableError


class StubDecisionEngine:
    """固定返回内部结果，验证 HTTP 层不绕过应用服务。"""

    def __init__(self) -> None:
        self.commands = []

    def review(self, command):  # noqa: ANN001
        self.commands.append(command)
        return DecisionResult(
            scenario_code=command.scenario_code or "court-evaluation-materials-review",
            scenario_name="委托评估机构申请材料核验",
            decision="pass",
            reasoning=("测试结果。",),
            citations=(
                AnswerCitationResult(
                    ref_no=1,
                    document_id=101,
                    version_id=201,
                    chunk_id=301,
                    policy_name="示例制度",
                    section_title="第十条",
                    page_no=1,
                    quote="示例规则片段。",
                ),
            ),
            used_fields=("申请书",),
            missing_input_fields=(),
            missing_fields=(),
            requirement_statuses=(
                RequirementStatusResult(
                    field_key="application_form",
                    label="申请书",
                    rule_matched=True,
                    submitted=True,
                    matched_rule_keywords=("申请书",),
                    matched_submission_items=("申请书",),
                    matched_components=("申请书",),
                    missing_components=(),
                ),
            ),
            debug=DecisionDebugResult(
                retrieval_query="申请参与委托评估的机构应提交哪些资料",
                policy_category="收费标准",
                provider="inline_submitted_materials",
                rule_hit_count=1,
                matched_rule_requirement_count=1,
                submitted_material_count=1,
                data_acquisition=DataAcquisitionDebugResult(
                    provider="inline_submitted_materials",
                    provided_input_fields=("已提交材料列表",),
                    missing_input_fields=(),
                    field_traces=(
                        DataFieldTraceResult(
                            field_key="submitted_materials",
                            label="已提交材料列表",
                            source="inline_submitted_materials",
                            provided=True,
                            value_count=1,
                        ),
                    ),
                ),
                retrieval_pipeline="test-pipeline",
                retrieval_strategy="test-strategy",
                retrieval_min_score=0.45,
                retrieval=(
                    DecisionRetrievalTrace(
                        name="fixture_recall",
                        source="fixture",
                        input_count=1,
                        output_count=1,
                    ),
                ),
            ),
        )


def test_policy_decision_http_route_returns_structured_response() -> None:
    engine = StubDecisionEngine()
    service = PolicyDecisionApplicationService(engine)
    application = create_app()
    application.dependency_overrides[get_policy_decision_application_service] = lambda: service

    response = TestClient(application).post(
        "/api/v1/kb/policy-decisions/court-evaluation-materials/review",
        json={"submitted_materials": ["申请书"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_code"] == "court-evaluation-materials-review"
    assert payload["decision"] == "pass"
    assert payload["citations"][0]["chunk_id"] == 301
    assert payload["debug"]["data_acquisition"]["provider"] == "inline_submitted_materials"
    assert engine.commands[0].submitted_materials == ("申请书",)
    assert engine.commands[0].submitted_materials_provided is True

    application.dependency_overrides.clear()


def test_policy_decision_http_route_supports_scenario_code() -> None:
    engine = StubDecisionEngine()
    service = PolicyDecisionApplicationService(engine)
    application = create_app()
    application.dependency_overrides[get_policy_decision_application_service] = lambda: service

    response = TestClient(application).post(
        "/api/v1/kb/policy-decisions/company-registration-review/review",
        json={"submitted_materials": ["登记证明"]},
    )

    assert response.status_code == 200
    assert response.json()["scenario_code"] == "company-registration-review"
    assert engine.commands[0].scenario_code == "company-registration-review"

    application.dependency_overrides.clear()


def test_policy_decision_http_maps_schema_unavailable_to_503() -> None:
    class SchemaUnavailableEngine:
        def review(self, command):  # noqa: ANN001
            raise KnowledgeBaseSchemaUnavailableError("请先初始化知识库表结构。")

    application = create_app()
    application.dependency_overrides[get_policy_decision_application_service] = lambda: (
        PolicyDecisionApplicationService(SchemaUnavailableEngine())
    )

    response = TestClient(application).post(
        "/api/v1/kb/policy-decisions/court-evaluation-materials/review",
        json={"submitted_materials": ["申请书"]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "请先初始化知识库表结构。"

    application.dependency_overrides.clear()
