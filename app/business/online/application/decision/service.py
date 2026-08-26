from __future__ import annotations

from app.business.online.application.data_acquisition import (
    ChecklistDataAcquisitionRequest,
    ChecklistDataProvider,
    ChecklistDataProviderRegistry,
    ChecklistInput,
    InlineChecklistDataProvider,
    PolicyDataAcquisitionService,
)
from app.business.online.application.decision.result_builder import DecisionResultBuilder
from app.business.online.application.rule_retrieval import (
    PolicyRuleRetrievalService,
    RetrievalSearcher,
    RuleRetrievalRequest,
)
from app.business.online.domain.checklist import (
    ChecklistScenarioDefinition,
    ChecklistScenarioRegistry,
    RuleDrivenChecklistPolicy,
)
from app.business.online.domain.decision_result import DecisionResult, DecisionReviewCommand


class RuleDrivenChecklistDecisionService:
    """编排规则检索、输入材料获取和领域评估，输出在线应用层结果。

    这里的两次“获取”职责不同：
    - ``rule_retrieval_service`` 从 Knowledge 查询能力获取 RAG 规则证据；
    - ``data_acquisition_service`` 获取本次决策需要核验的业务输入材料。

    本服务只负责应用层流程编排，不直接访问数据库、向量索引或具体 Provider。
    """

    def __init__(
        self,
        retrieval_service: RetrievalSearcher,
        *,
        decision_policy: RuleDrivenChecklistPolicy | None = None,
        data_provider: ChecklistDataProvider | None = None,
        scenario_registry: ChecklistScenarioRegistry,
        rule_retrieval_service: PolicyRuleRetrievalService | None = None,
        data_acquisition_service: PolicyDataAcquisitionService | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.decision_policy = decision_policy or RuleDrivenChecklistPolicy()
        self.scenario_registry = scenario_registry
        self.rule_retrieval_service = rule_retrieval_service or PolicyRuleRetrievalService(
            retrieval_service,
            scenario_registry=self.scenario_registry,
            checklist_policy=self.decision_policy,
        )
        self.data_acquisition_service = data_acquisition_service or (
            self._build_data_acquisition_service(data_provider)
        )

    def review(self, command: DecisionReviewCommand) -> DecisionResult:
        """执行一次规则驱动的 Checklist 决策。

        决策必须先确认规则证据，再确认业务输入，最后交给领域策略判断。
        任一前置条件不足时直接返回“证据不足”，避免在依据不完整时生成通过或失败结论。
        """
        scenario = self._resolve_scenario(command.scenario_code)
        builder = DecisionResultBuilder(scenario=scenario)

        # 规则证据来自 Knowledge/RAG。这里不直接执行向量检索，
        # 而是通过 Rule Retrieval 应用服务将检索结果整理成 Checklist 可消费的 RulePack。
        rule_pack = self.rule_retrieval_service.retrieve_rule_pack(
            RuleRetrievalRequest(
                scenario_code=scenario.scenario_code,
                top_k=command.top_k,
                document_id=command.document_id,
                include_history=command.include_history,
            )
        )

        # 业务输入与规则证据分开获取：data_acquisition 只负责收集和规范化
        # 本次请求中的 Checklist 材料，不负责从知识库检索规则。
        data_pack = self.data_acquisition_service.acquire_checklist_data(
            ChecklistDataAcquisitionRequest(
                scenario_code=scenario.scenario_code,
                checklist_request=ChecklistInput(
                    submitted_materials=command.submitted_materials,
                    provided_fields=(
                        frozenset({scenario.input_field_key})
                        if command.submitted_materials_provided
                        else frozenset()
                    ),
                ),
                input_field_key=scenario.input_field_key,
                input_field_label=scenario.input_field_label,
            )
        )

        # 调试信息和规则要求状态在所有返回分支中都要保留，
        # 这样规则不足、输入不足和正常评估都能追溯各自的来源。
        debug = builder.build_debug_info(
            retrieval_debug=rule_pack.retrieval_debug,
            retrieval_pipeline=rule_pack.retrieval_pipeline,
            retrieval_strategy=rule_pack.retrieval_strategy,
            retrieval_min_score=rule_pack.retrieval_min_score,
            rule_hit_count=rule_pack.rule_hit_count,
            rule_match_count=rule_pack.matched_requirement_count,
            data_pack=data_pack,
        )
        requirement_statuses = builder.build_requirement_statuses_from_rule_pack(
            rule_pack.checklist_rule_pack
        )

        # 没有足够的规则命中时，无法确定本场景到底要求哪些材料，
        # 因此不能继续做材料通过性判断。
        if not rule_pack.is_sufficient:
            return builder.build_response(
                decision="insufficient_evidence",
                reasoning=builder.build_rule_insufficient_reasoning(
                    rule_pack.insufficient_reason
                ),
                citations=rule_pack.citations,
                used_fields=(),
                missing_input_fields=tuple(data_pack.missing_input_fields),
                missing_fields=(),
                requirement_statuses=requirement_statuses,
                debug=debug,
            )

        # 规则已经明确，但本次请求没有提供必要的业务输入，
        # 这里返回输入不足，而不是把它误判为材料不合格。
        if not data_pack.is_sufficient:
            return builder.build_response(
                decision="insufficient_evidence",
                reasoning=builder.build_data_insufficient_reasoning(
                    data_pack.insufficient_reason
                ),
                citations=rule_pack.citations,
                used_fields=(),
                missing_input_fields=tuple(data_pack.missing_input_fields),
                missing_fields=(),
                requirement_statuses=requirement_statuses,
                debug=debug,
            )

        # 前置数据完整后，才进入 Domain Policy：将已提交材料与规则要求逐项匹配。
        evaluation = self.decision_policy.evaluate_submission(
            rule_pack=rule_pack.checklist_rule_pack,
            submitted_items=list(data_pack.submitted_materials),
        )
        missing_fields = tuple(evaluation.missing_field_labels)
        decision = "pass" if not missing_fields else "fail"

        # 决策结论由领域策略产生；Builder 只负责将领域结果、引用和调试信息
        # 组装成应用层返回对象，不在这里重新实现业务判断。
        return builder.build_response(
            decision=decision,
            reasoning=builder.build_reasoning(
                matched_requirement_count=rule_pack.matched_requirement_count,
                submitted_value_count=len(data_pack.submitted_materials),
                missing_fields=list(missing_fields),
            ),
            citations=rule_pack.citations,
            used_fields=tuple(evaluation.used_field_labels),
            missing_input_fields=(),
            missing_fields=missing_fields,
            requirement_statuses=builder.build_requirement_statuses_from_evaluation(evaluation),
            debug=debug,
        )

    def _resolve_scenario(self, scenario_code: str | None) -> ChecklistScenarioDefinition:
        """解析请求场景；未传场景编码时使用 Composition Root 配置的默认场景。"""
        normalized_code = (scenario_code or "").strip()
        if not normalized_code:
            return self.scenario_registry.default()
        return self.scenario_registry.get(normalized_code)

    def _build_data_acquisition_service(
        self,
        data_provider: ChecklistDataProvider | None,
    ) -> PolicyDataAcquisitionService:
        """为兼容直接构造服务的调用方，创建并装配默认输入材料 Provider。

        正式运行时通常由 Composition Root 注入完整的 Provider Registry；
        这里的备用装配主要服务于测试和旧调用路径。当前所有场景使用同一个
        inline Provider，未来可在 Composition Root 按场景注册不同来源的 Provider。
        """
        provider = data_provider or InlineChecklistDataProvider()
        registry = ChecklistDataProviderRegistry(default_provider=provider)
        for scenario in self.scenario_registry.list_all():
            registry.register(scenario.scenario_code, provider)
        return PolicyDataAcquisitionService(registry)
