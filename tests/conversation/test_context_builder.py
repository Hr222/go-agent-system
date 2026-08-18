from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from app.composition.conversation import build_conversation_context_builder
from app.modules.conversation.application import ConversationContextBuilder
from app.modules.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Message,
    MessageRole,
)
from app.modules.conversation.errors import ContextBudgetExceededError


def _message(
    conversation_id: UUID,
    sequence: int,
    content: str = "消息",
    role: MessageRole = MessageRole.USER,
) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=sequence,
    )


class FixedCostEstimator:
    def __init__(self, costs: Mapping[int, object]) -> None:
        self.costs = costs
        self.sequences: list[int] = []

    def estimate_cost(self, message) -> object:
        self.sequences.append(message.sequence)
        return self.costs[message.sequence]


def test_context_builder_returns_empty_context_for_empty_window() -> None:
    conversation_id = uuid4()

    context = build_conversation_context_builder().build(
        conversation_id=conversation_id,
        messages=(),
        policy=ContextPolicy(max_messages=3),
        budget=ContextBudget(max_cost=10),
    )

    assert context.conversation_id == conversation_id
    assert context.messages == ()
    assert context.used_cost == 0
    assert context.omitted_message_count == 0


def test_context_builder_preserves_source_fields_and_order() -> None:
    conversation_id = uuid4()
    messages = (
        _message(conversation_id, 1, "甲", MessageRole.SYSTEM),
        _message(conversation_id, 2, "乙", MessageRole.USER),
        _message(conversation_id, 3, "丙", MessageRole.ASSISTANT),
    )

    context = build_conversation_context_builder().build(
        conversation_id=conversation_id,
        messages=messages,
        policy=ContextPolicy(max_messages=3),
        budget=ContextBudget(max_cost=10),
    )

    assert [message.sequence for message in context.messages] == [1, 2, 3]
    assert [message.source_message_id for message in context.messages] == [
        message.id for message in messages
    ]
    assert [message.role for message in context.messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert [message.content for message in context.messages] == ["甲", "乙", "丙"]
    assert context.used_cost == 3
    assert context.omitted_message_count == 0


def test_context_builder_prefers_newest_messages_with_message_limit() -> None:
    conversation_id = uuid4()
    messages = tuple(_message(conversation_id, sequence) for sequence in range(1, 5))

    context = build_conversation_context_builder().build(
        conversation_id=conversation_id,
        messages=messages,
        policy=ContextPolicy(max_messages=2),
        budget=ContextBudget(max_cost=10),
    )

    assert [message.sequence for message in context.messages] == [3, 4]
    assert context.omitted_message_count == 2


def test_context_builder_stops_at_first_older_message_that_exceeds_budget() -> None:
    conversation_id = uuid4()
    messages = (
        _message(conversation_id, 1, "11111"),
        _message(conversation_id, 2, "22222"),
        _message(conversation_id, 3, "333"),
        _message(conversation_id, 4, "444"),
    )

    context = build_conversation_context_builder().build(
        conversation_id=conversation_id,
        messages=messages,
        policy=ContextPolicy(max_messages=4),
        budget=ContextBudget(max_cost=6),
    )

    assert [message.sequence for message in context.messages] == [3, 4]
    assert context.used_cost == 6
    assert context.omitted_message_count == 2


def test_context_builder_rejects_latest_message_that_exceeds_budget() -> None:
    conversation_id = uuid4()

    with pytest.raises(ContextBudgetExceededError, match="最新上下文消息"):
        build_conversation_context_builder().build(
            conversation_id=conversation_id,
            messages=(_message(conversation_id, 1, "超过预算"),),
            policy=ContextPolicy(max_messages=1),
            budget=ContextBudget(max_cost=3),
        )


@pytest.mark.parametrize("max_messages", [0, -1, True, 1.0])
def test_context_policy_rejects_invalid_message_limits(max_messages: object) -> None:
    with pytest.raises(ValueError, match="消息数量上限"):
        ContextPolicy(max_messages=max_messages)  # type: ignore[arg-type]


@pytest.mark.parametrize("max_cost", [0, -1, True, 1.0])
def test_context_budget_rejects_invalid_cost_limits(max_cost: object) -> None:
    with pytest.raises(ValueError, match="成本上限"):
        ContextBudget(max_cost=max_cost)  # type: ignore[arg-type]


def test_context_builder_rejects_messages_from_another_conversation() -> None:
    conversation_id = uuid4()

    with pytest.raises(ValueError, match="其他会话"):
        build_conversation_context_builder().build(
            conversation_id=conversation_id,
            messages=(_message(uuid4(), 1),),
            policy=ContextPolicy(max_messages=1),
            budget=ContextBudget(max_cost=10),
        )


def test_context_builder_rejects_out_of_order_messages() -> None:
    conversation_id = uuid4()

    with pytest.raises(ValueError, match="严格递增"):
        build_conversation_context_builder().build(
            conversation_id=conversation_id,
            messages=(
                _message(conversation_id, 2),
                _message(conversation_id, 1),
            ),
            policy=ContextPolicy(max_messages=2),
            budget=ContextBudget(max_cost=10),
        )


@pytest.mark.parametrize("cost", [-1, True, 1.5])
def test_context_builder_rejects_invalid_estimator_cost(cost: object) -> None:
    conversation_id = uuid4()
    estimator = FixedCostEstimator({1: cost})

    with pytest.raises(ValueError, match="成本必须是非负整数"):
        ConversationContextBuilder(estimator).build(
            conversation_id=conversation_id,
            messages=(_message(conversation_id, 1),),
            policy=ContextPolicy(max_messages=1),
            budget=ContextBudget(max_cost=10),
        )


def test_context_builder_accepts_replaceable_cost_estimator() -> None:
    conversation_id = uuid4()
    estimator = FixedCostEstimator({1: 7, 2: 2, 3: 2})

    context = ConversationContextBuilder(estimator).build(
        conversation_id=conversation_id,
        messages=tuple(_message(conversation_id, sequence) for sequence in range(1, 4)),
        policy=ContextPolicy(max_messages=3),
        budget=ContextBudget(max_cost=4),
    )

    assert [message.sequence for message in context.messages] == [2, 3]
    assert context.used_cost == 4
    assert context.omitted_message_count == 1
    assert estimator.sequences == [3, 2, 1]
