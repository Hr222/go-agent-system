from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.composition.dialogue import build_basic_dialogue_runtime
from app.modules.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationContextBuilder,
)
from app.modules.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Conversation,
    Message,
    MessageRole,
)
from app.modules.conversation.errors import ContextBudgetExceededError
from app.modules.conversation.ports import ConversationHistoryPage
from app.modules.dialogue.application import BasicDialogueRuntime, DialogueCommand
from app.modules.llm.contracts import ChatLlmResult


def _message(
    conversation_id: UUID,
    sequence: int,
    role: MessageRole,
    content: str,
) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=sequence,
        created_at=datetime.now(timezone.utc),
    )


class FakeConversationWriter:
    def __init__(
        self,
        conversation_id: UUID,
        messages: list[Message] | None = None,
        *,
        fail_assistant_write: bool = False,
    ) -> None:
        self.conversation_id = conversation_id
        self.messages = list(messages or [])
        self.fail_assistant_write = fail_assistant_write

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        if conversation_id != self.conversation_id:
            raise RuntimeError("会话不存在")
        if role is MessageRole.ASSISTANT and self.fail_assistant_write:
            raise RuntimeError("助手消息写入失败")
        message = _message(
            conversation_id,
            len(self.messages) + 1,
            role,
            content,
        )
        self.messages.append(message)
        return message


class FakeConversationReader:
    def __init__(self, writer: FakeConversationWriter) -> None:
        self.writer = writer
        self.calls: list[tuple[int, int | None]] = []

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None = None,
    ) -> ConversationHistoryPage:
        if conversation_id != self.writer.conversation_id:
            raise RuntimeError("会话不存在")
        self.calls.append((limit, after_sequence))
        records = [
            message
            for message in self.writer.messages
            if after_sequence is None or message.sequence > after_sequence
        ]
        page_messages = tuple(records[:limit])
        has_more = len(records) > limit
        return ConversationHistoryPage(
            conversation=Conversation(id=conversation_id, owner_subject="user-1"),
            messages=page_messages,
            has_more=has_more,
            next_after_sequence=page_messages[-1].sequence if has_more else None,
        )


class FakeChatLlm:
    def __init__(
        self,
        result: ChatLlmResult | Exception = ChatLlmResult(
            content="默认回答",
            model="dialogue-test",
            prompt_version="dialogue-basic-chat-v1",
        ),
    ) -> None:
        self.result = result
        self.requests = []

    def invoke(self, request):  # noqa: ANN001
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class RuntimeHarness:
    runtime: BasicDialogueRuntime
    writer: FakeConversationWriter
    reader: FakeConversationReader
    llm: FakeChatLlm


def _runtime(
    *,
    messages: list[Message] | None = None,
    llm_result: ChatLlmResult | Exception | None = None,
    policy: ContextPolicy = ContextPolicy(max_messages=3),
    budget: ContextBudget = ContextBudget(max_cost=100),
    fail_assistant_write: bool = False,
) -> RuntimeHarness:
    conversation_id = messages[0].conversation_id if messages else uuid4()
    writer = FakeConversationWriter(
        conversation_id,
        messages,
        fail_assistant_write=fail_assistant_write,
    )
    reader = FakeConversationReader(writer)
    llm = FakeChatLlm(llm_result or FakeChatLlm().result)
    runtime = BasicDialogueRuntime(
        conversation_writer=writer,  # type: ignore[arg-type]
        conversation_reader=reader,  # type: ignore[arg-type]
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=llm,
        context_policy=policy,
        context_budget=budget,
    )
    return RuntimeHarness(runtime=runtime, writer=writer, reader=reader, llm=llm)


def test_runtime_persists_messages_and_sends_ordered_history() -> None:
    conversation_id = uuid4()
    harness = _runtime(
        messages=[
            _message(conversation_id, 1, MessageRole.USER, "前一个问题"),
            _message(conversation_id, 2, MessageRole.ASSISTANT, "前一个回答"),
        ],
        llm_result=ChatLlmResult(
            content="  本轮回答  ",
            model="glm-dialogue",
            prompt_version="dialogue-basic-chat-v1",
            input_tokens=11,
            output_tokens=7,
            total_tokens=18,
        ),
    )

    result = harness.runtime.execute(
        DialogueCommand(conversation_id=conversation_id, message="  本轮问题  ")
    )

    assert [message.sequence for message in harness.writer.messages] == [1, 2, 3, 4]
    assert [message.role for message in harness.writer.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert result.user_message.content == "本轮问题"
    assert result.assistant_message.content == "本轮回答"
    assert result.model == "glm-dialogue"
    assert result.total_tokens == 18
    assert [message.sequence for message in result.context.messages] == [1, 2, 3]
    request = harness.llm.requests[0]
    assert [(message.role.value, message.content) for message in request.history_messages] == [
        ("user", "前一个问题"),
        ("assistant", "前一个回答"),
    ]
    assert request.user_prompt == "本轮问题"
    assert [message.content for message in request.history_messages].count("本轮问题") == 0


def test_runtime_scans_all_pages_and_keeps_latest_context_window() -> None:
    conversation_id = uuid4()
    history = [
        _message(
            conversation_id,
            sequence,
            MessageRole.USER if sequence % 2 else MessageRole.ASSISTANT,
            f"消息 {sequence}",
        )
        for sequence in range(1, 206)
    ]
    harness = _runtime(messages=history, policy=ContextPolicy(max_messages=3))

    result = harness.runtime.execute(
        DialogueCommand(conversation_id=conversation_id, message="最新问题")
    )

    assert harness.reader.calls == [(200, None), (200, 200)]
    assert [message.sequence for message in result.context.messages] == [204, 205, 206]
    request = harness.llm.requests[0]
    assert [message.content for message in request.history_messages] == ["消息 204", "消息 205"]
    assert request.user_prompt == "最新问题"


def test_runtime_rejects_blank_input_without_persisting_or_calling_llm() -> None:
    harness = _runtime()

    with pytest.raises(ValueError, match="消息内容不能为空"):
        harness.runtime.execute(
            DialogueCommand(conversation_id=harness.writer.conversation_id, message=" \n ")
        )

    assert harness.writer.messages == []
    assert harness.llm.requests == []


def test_runtime_keeps_user_message_when_llm_fails() -> None:
    harness = _runtime(llm_result=RuntimeError("模型失败"))

    with pytest.raises(RuntimeError, match="模型失败"):
        harness.runtime.execute(
            DialogueCommand(conversation_id=harness.writer.conversation_id, message="问题")
        )

    assert [(message.role, message.content) for message in harness.writer.messages] == [
        (MessageRole.USER, "问题")
    ]


def test_runtime_keeps_user_message_when_model_response_is_empty() -> None:
    harness = _runtime(
        llm_result=ChatLlmResult(
            content="  ",
            model="glm-dialogue",
            prompt_version="dialogue-basic-chat-v1",
        )
    )

    with pytest.raises(RuntimeError, match="空响应"):
        harness.runtime.execute(
            DialogueCommand(conversation_id=harness.writer.conversation_id, message="问题")
        )

    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_runtime_keeps_user_message_when_context_budget_is_exceeded() -> None:
    harness = _runtime(budget=ContextBudget(max_cost=1))

    with pytest.raises(ContextBudgetExceededError, match="最新上下文消息"):
        harness.runtime.execute(
            DialogueCommand(conversation_id=harness.writer.conversation_id, message="超过预算")
        )

    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]
    assert harness.llm.requests == []


def test_runtime_keeps_user_message_when_assistant_write_fails() -> None:
    harness = _runtime(fail_assistant_write=True)

    with pytest.raises(RuntimeError, match="助手消息写入失败"):
        harness.runtime.execute(
            DialogueCommand(conversation_id=harness.writer.conversation_id, message="问题")
        )

    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]
    assert len(harness.llm.requests) == 1


def test_basic_dialogue_composition_can_be_built_without_calling_infrastructure() -> None:
    runtime = build_basic_dialogue_runtime(
        object(),  # type: ignore[arg-type]
        FakeChatLlm(),
    )

    assert isinstance(runtime, BasicDialogueRuntime)
