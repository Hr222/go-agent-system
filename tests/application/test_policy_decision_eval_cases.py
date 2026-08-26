from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.business.online.application.decision import RuleDrivenChecklistDecisionService
from app.business.online.domain.checklist import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "application"
    / "fixtures"
    / "policy_decision_eval_cases.json"
)
EVAL_CASES: list[dict[str, Any]] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class FixtureRetrievalService:
    """用固定规则片段验证 D5 场景，不依赖外部 embedding 或 LLM 服务。"""

    def __init__(self, chunk_text: str) -> None:
        self.chunk_text = chunk_text

    def search(self, request):  # noqa: ANN001
        hit = RetrievalHit(
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
            chunk_text=self.chunk_text,
            score=1.0,
            rank=1,
            retrieval_source="hybrid",
            score_breakdown={"keyword": 1.0},
        )
        return RetrievalSearchResponse(
            query=request.query,
            top_k=request.top_k,
            filters=RetrievalFilters(
                policy_category=request.policy_category,
                responsible_department=request.responsible_department,
                document_id=request.document_id,
                include_history=request.include_history,
            ),
            hits=[hit],
            debug=RetrievalDebugInfo(
                pipeline="test-pipeline",
                strategy="test-strategy",
                min_score=0.45,
                stages=[
                    RetrievalStageDebug(
                        name="fixture_recall",
                        source="fixture",
                        input_count=1,
                        output_count=1,
                    )
                ],
            ),
        )


@pytest.mark.parametrize("case", EVAL_CASES, ids=lambda case: case["case_id"])
def test_policy_decision_fixture_case_matches_expected_result(case: dict[str, Any]) -> None:
    service = RuleDrivenChecklistDecisionService(
        FixtureRetrievalService(case["retrieval_text"]),
        scenario_registry=ChecklistScenarioRegistry(
            definitions=(COURT_EVALUATION_MATERIALS_SCENARIO,)
        ),
    )

    response = service.review(
        DecisionReviewCommand(
            submitted_materials=tuple(case["submitted_materials"]),
            submitted_materials_provided=case["submitted_materials_provided"],
        )
    )

    expected = case["expected"]
    assert response.decision == expected["decision"]
    assert list(response.missing_input_fields) == expected["missing_input_fields"]
    assert list(response.missing_fields) == expected["missing_fields"]
    assert len(response.used_fields) == expected["used_fields_count"]
    assert len(response.citations) == expected["citation_count"]
