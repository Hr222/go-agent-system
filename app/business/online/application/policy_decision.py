from __future__ import annotations

from typing import Protocol

from app.business.online.domain.decision_result import DecisionResult, DecisionReviewCommand


class PolicyDecisionEngine(Protocol):
    def review(self, command: DecisionReviewCommand) -> DecisionResult: ...


class PolicyDecisionApplicationService:
    """在线决策用例入口，只编排内部 Command/Result。"""

    def __init__(self, engine: PolicyDecisionEngine) -> None:
        self.engine = engine

    def review(self, command: DecisionReviewCommand) -> DecisionResult:
        if command.top_k < 1:
            raise ValueError("规则检索 top_k 必须为正整数。")
        return self.engine.review(command)
