from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ChecklistRequirementComponent:
    """组成单项材料要求的最小匹配单元。"""

    label: str
    aliases: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ChecklistRequirementDefinition:
    """描述一项材料要求的字段名、展示名与匹配关键词。"""

    field_key: str
    label: str
    components: tuple[ChecklistRequirementComponent, ...]
    evidence_keywords: tuple[str, ...]
    required: bool = True


@dataclass(slots=True, frozen=True)
class ChecklistScenarioDefinition:
    """定义某个核验场景的检索语义与要求清单。"""

    scenario_code: str
    scenario_name: str
    retrieval_query: str
    policy_category: str | None
    requirements: tuple[ChecklistRequirementDefinition, ...]
    min_rule_match_count: int = 1
    input_field_key: str = "submitted_materials"
    input_field_label: str = "已提交材料列表"


@dataclass(slots=True, frozen=True)
class ChecklistRequirementEvidence:
    """记录单项要求在命中规则中的证据情况。"""

    definition: ChecklistRequirementDefinition
    matched_rule_keywords: tuple[str, ...]

    @property
    def rule_matched(self) -> bool:
        return bool(self.matched_rule_keywords)


@dataclass(slots=True, frozen=True)
class ChecklistRulePack:
    """将检索出的规则片段归并为当前场景的规则包。"""

    scenario: ChecklistScenarioDefinition
    requirements: tuple[ChecklistRequirementEvidence, ...]

    @property
    def matched_requirement_count(self) -> int:
        return sum(1 for item in self.requirements if item.rule_matched)

    @property
    def is_sufficient(self) -> bool:
        return self.matched_requirement_count >= self.scenario.min_rule_match_count


@dataclass(slots=True, frozen=True)
class ChecklistRequirementDecision:
    """记录单项材料在本次提交中的命中与缺失情况。"""

    evidence: ChecklistRequirementEvidence
    submitted: bool
    matched_submission_items: tuple[str, ...]
    matched_components: tuple[str, ...]
    missing_components: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ChecklistEvaluationResult:
    """汇总整份材料清单的核验结论。"""

    scenario: ChecklistScenarioDefinition
    decisions: tuple[ChecklistRequirementDecision, ...]

    @property
    def used_field_labels(self) -> list[str]:
        return [
            item.evidence.definition.label
            for item in self.decisions
            if item.evidence.rule_matched and item.submitted
        ]

    @property
    def missing_field_labels(self) -> list[str]:
        return [
            item.evidence.definition.label
            for item in self.decisions
            if item.evidence.rule_matched
            and item.evidence.definition.required
            and not item.submitted
        ]


class RuleDrivenChecklistPolicy:
    """基于规则片段抽取材料清单并完成提交核验。"""

    _normalize_pattern = re.compile(r"[\s\u3000()（）\[\]【】,，。:：;；、\-_]+")

    def build_rule_pack(
        self,
        *,
        scenario: ChecklistScenarioDefinition,
        rule_texts: list[str],
    ) -> ChecklistRulePack:
        """把命中的规则正文归并成结构化材料要求。"""
        normalized_rule_text = self._normalize_text("\n".join(rule_texts))
        requirement_evidences: list[ChecklistRequirementEvidence] = []
        for requirement in scenario.requirements:
            matched_keywords = tuple(
                keyword
                for keyword in requirement.evidence_keywords
                if self._normalize_text(keyword) in normalized_rule_text
            )
            requirement_evidences.append(
                ChecklistRequirementEvidence(
                    definition=requirement,
                    matched_rule_keywords=matched_keywords,
                )
            )

        return ChecklistRulePack(
            scenario=scenario,
            requirements=tuple(requirement_evidences),
        )

    def evaluate_submission(
        self,
        *,
        rule_pack: ChecklistRulePack,
        submitted_items: list[str],
    ) -> ChecklistEvaluationResult:
        """按照材料组件逐项核对本次提交是否完整。"""
        normalized_submitted_items = [
            (item.strip(), self._normalize_text(item))
            for item in submitted_items
            if item and item.strip()
        ]
        decisions: list[ChecklistRequirementDecision] = []
        for evidence in rule_pack.requirements:
            matched_submission_items: list[str] = []
            matched_components: list[str] = []
            missing_components: list[str] = []

            for component in evidence.definition.components:
                component_aliases = [self._normalize_text(alias) for alias in component.aliases]
                matched_raw_items = [
                    raw_item
                    for raw_item, normalized_item in normalized_submitted_items
                    if any(
                        alias in normalized_item or normalized_item in alias
                        for alias in component_aliases
                    )
                ]
                if matched_raw_items:
                    matched_components.append(component.label)
                    for raw_item in matched_raw_items:
                        if raw_item not in matched_submission_items:
                            matched_submission_items.append(raw_item)
                else:
                    missing_components.append(component.label)

            decisions.append(
                ChecklistRequirementDecision(
                    evidence=evidence,
                    submitted=evidence.rule_matched and not missing_components,
                    matched_submission_items=tuple(matched_submission_items),
                    matched_components=tuple(matched_components),
                    missing_components=tuple(missing_components),
                )
            )

        return ChecklistEvaluationResult(
            scenario=rule_pack.scenario,
            decisions=tuple(decisions),
        )

    def _normalize_text(self, value: str) -> str:
        """统一去掉空白与常见标点，降低别名匹配噪声。"""
        lowered = value.lower().strip()
        return self._normalize_pattern.sub("", lowered)
