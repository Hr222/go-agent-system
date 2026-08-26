from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.platform.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Message,
    ModelContext,
    ModelContextMessage,
)
from app.platform.conversation.errors import ContextBudgetExceededError
from app.platform.conversation.ports import ContextMessageCostEstimator


class CharacterCountContextMessageCostEstimator:
    """按消息内容字符数提供确定性的默认成本计量。"""

    def estimate_cost(self, message: ModelContextMessage) -> int:
        return len(message.content)


class ConversationContextBuilder:
    """将单个会话的有序消息窗口选择为模型中立上下文。"""

    def __init__(self, cost_estimator: ContextMessageCostEstimator) -> None:
        self.cost_estimator = cost_estimator

    def build(
        self,
        *,
        conversation_id: UUID,
        messages: Sequence[Message],
        policy: ContextPolicy,
        budget: ContextBudget,
    ) -> ModelContext:
        """选择最新连续消息后缀，并保持消息的原始正序。"""

        self._validate_request(
            conversation_id=conversation_id,
            messages=messages,
            policy=policy,
            budget=budget,
        )
        context_messages = tuple(
            ModelContextMessage.from_message(message) for message in messages
        )
        candidates = context_messages[-policy.max_messages :]

        selected_reversed: list[ModelContextMessage] = []
        used_cost = 0
        for message in reversed(candidates):
            cost = self._estimate_cost(message)
            if used_cost + cost > budget.max_cost:
                if not selected_reversed:
                    raise ContextBudgetExceededError(
                        "最新上下文消息的成本超过可用预算。"
                    )
                break
            selected_reversed.append(message)
            used_cost += cost

        selected_messages = tuple(reversed(selected_reversed))
        return ModelContext(
            conversation_id=conversation_id,
            messages=selected_messages,
            budget=budget,
            used_cost=used_cost,
            omitted_message_count=len(context_messages) - len(selected_messages),
        )

    def _validate_request(
        self,
        *,
        conversation_id: UUID,
        messages: Sequence[Message],
        policy: ContextPolicy,
        budget: ContextBudget,
    ) -> None:
        if not isinstance(conversation_id, UUID):
            raise ValueError("上下文会话标识必须是 UUID。")
        if not isinstance(policy, ContextPolicy):
            raise ValueError("上下文策略无效。")
        if not isinstance(budget, ContextBudget):
            raise ValueError("上下文预算无效。")

        previous_sequence = 0
        for message in messages:
            if not isinstance(message, Message):
                raise ValueError("上下文历史包含无效消息。")
            if message.conversation_id != conversation_id:
                raise ValueError("上下文历史包含其他会话的消息。")
            if message.sequence <= previous_sequence:
                raise ValueError("上下文历史消息必须按顺序号严格递增。")
            previous_sequence = message.sequence

    def _estimate_cost(self, message: ModelContextMessage) -> int:
        cost = self.cost_estimator.estimate_cost(message)
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise ValueError("上下文消息成本必须是非负整数。")
        return cost
