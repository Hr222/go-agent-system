from __future__ import annotations

from app.business.online.application.rule_retrieval import (
    PolicyRuleRetrievalService,
    RuleRetrievalRequest,
)
from app.business.online.domain.checklist import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
    ChecklistScenarioRegistry,
)
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
    """使用固定检索结果替代真实检索，便于验证规则获取层。"""

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
        source_path="D:/knowledge/court-policy.docx",
        file_name="court-policy.docx",
        retrieval_source="hybrid",
        score_breakdown={"keyword": 1.0},
    )


def _scenario_registry() -> ChecklistScenarioRegistry:
    """为规则获取测试显式提供场景定义。"""
    return ChecklistScenarioRegistry(definitions=(COURT_EVALUATION_MATERIALS_SCENARIO,))


def test_rule_retrieval_service_builds_rule_pack_for_registered_scenario() -> None:
    service = PolicyRuleRetrievalService(
        FakeRetrievalService([_make_hit(RULE_CHUNK_TEXT)]),
        scenario_registry=_scenario_registry(),
    )

    rule_pack = service.retrieve_rule_pack(
        RuleRetrievalRequest(
            scenario_code="court-evaluation-materials-review",
            top_k=5,
            document_id=None,
            include_history=False,
        )
    )

    assert rule_pack.scenario_code == "court-evaluation-materials-review"
    assert rule_pack.rule_hit_count == 1
    assert rule_pack.matched_requirement_count == 8
    assert rule_pack.is_sufficient is True
    assert rule_pack.insufficient_reason is None
    assert len(rule_pack.citations) == 1
    assert rule_pack.citations[0].source_path == "D:/knowledge/court-policy.docx"
    assert rule_pack.citations[0].file_name == "court-policy.docx"


def test_rule_retrieval_service_returns_unified_insufficient_reason() -> None:
    service = PolicyRuleRetrievalService(
        FakeRetrievalService([_make_hit("申请参与委托评估的机构应提交资料，具体要求以法院通知为准。")]),
        scenario_registry=_scenario_registry(),
    )

    rule_pack = service.retrieve_rule_pack(
        RuleRetrievalRequest(
            scenario_code="court-evaluation-materials-review",
            top_k=5,
            document_id=None,
            include_history=False,
        )
    )

    assert rule_pack.is_sufficient is False
    assert rule_pack.matched_requirement_count < 8
    assert rule_pack.insufficient_reason is not None
