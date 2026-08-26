from __future__ import annotations

from dataclasses import dataclass

from app.business.online.contracts import AnswerCitationResult
from app.business.online.domain.checklist import ChecklistRulePack, ChecklistScenarioDefinition
from app.platform.knowledge.ports.read_port import KnowledgeQueryTrace, KnowledgeSearchHit


@dataclass(slots=True, frozen=True)
class RulePack:
    """面向决策用例的规则证据包。"""

    scenario: ChecklistScenarioDefinition
    original_query: str
    matched_rule_chunks: tuple[KnowledgeSearchHit, ...]
    citations: tuple[AnswerCitationResult, ...]
    retrieval_debug: tuple[KnowledgeQueryTrace, ...]
    retrieval_pipeline: str
    retrieval_strategy: str
    retrieval_min_score: float
    matched_requirement_count: int
    is_sufficient: bool
    insufficient_reason: str | None
    checklist_rule_pack: ChecklistRulePack

    @property
    def scenario_code(self) -> str:
        return self.scenario.scenario_code

    @property
    def scenario_name(self) -> str:
        return self.scenario.scenario_name

    @property
    def rule_hit_count(self) -> int:
        return len(self.matched_rule_chunks)
