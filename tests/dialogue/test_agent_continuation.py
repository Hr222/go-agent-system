from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.modules.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationAccessService,
    ConversationContextBuilder,
    ConversationHistoryReadService,
    ConversationWriteService,
)
from app.modules.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Conversation,
    ConversationEvent,
    Message,
    MessageRole,
)
from app.modules.conversation.ports import ConversationHistoryPage
from app.modules.dialogue.application import (
    DialogueAgentContinuationCommand,
    DialogueAgentContinuationService,
)
from app.modules.llm.contracts import ChatLlmResult
from app.modules.security.domain.principal import RequestPrincipal


def _message(
    conversation_id: UUID,
    sequence: int,
    role: MessageRole,
    content: str,
) -> Message:
    return Message(
        conversation_id=conversation_id,
        sequence=sequence,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )


class FakeConversationReadPort:
    def __init__(self, conversation_id: UUID, messages: list[Message]) -> None:
        self.conversation_id = conversation_id
        self.messages = messages

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage:
        if conversation_id != self.conversation_id:
            raise LookupError("conversation missing")
        candidates = [
            message
            for message in self.messages
            if after_sequence is None or message.sequence > after_sequence
        ]
        page_messages = tuple(candidates[:limit])
        return ConversationHistoryPage(
            conversation=Conversation(id=conversation_id, owner_subject="user-1"),
            messages=page_messages,
            has_more=len(candidates) > limit,
            next_after_sequence=page_messages[-1].sequence
            if len(candidates) > limit
            else None,
        )


class FakeConversationWritePort:
    def __init__(self, conversation_id: UUID, messages: list[Message]) -> None:
        self.conversation_id = conversation_id
        self.messages = messages
        self.access_queries: list[tuple[UUID, str]] = []

    def save_conversation(self, conversation: Conversation) -> Conversation:
        return conversation

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        if conversation_id != self.conversation_id:
            raise LookupError("conversation missing")
        message = _message(
            conversation_id,
            len(self.messages) + 1,
            role,
            content,
        )
        self.messages.append(message)
        return message

    def get_owned_conversation(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
    ) -> Conversation | None:
        self.access_queries.append((conversation_id, owner_subject))
        if conversation_id != self.conversation_id or owner_subject != "user-1":
            return None
        return Conversation(id=conversation_id, owner_subject=owner_subject)


class FakeEventReadPort:
    def __init__(self, events: list[ConversationEvent]) -> None:
        self.events = events
        self.calls: list[tuple[UUID, str | None]] = []

    def list_events(
        self,
        *,
        conversation_id: UUID,
        call_id: str | None = None,
    ) -> tuple[ConversationEvent, ...]:
        self.calls.append((conversation_id, call_id))
        return tuple(
            event
            for event in self.events
            if event.conversation_id == conversation_id
            and (call_id is None or event.call_id == call_id)
        )


class FakeChatLlm:
    def __init__(self, result: ChatLlmResult | Exception) -> None:
        self.result = result
        self.requests = []

    def invoke(self, request):  # noqa: ANN001
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class ContinuationHarness:
    service: DialogueAgentContinuationService
    writer: FakeConversationWritePort
    events: FakeEventReadPort
    llm: FakeChatLlm
    conversation_id: UUID


def _event(
    conversation_id: UUID,
    *,
    call_id: str = "call-1",
    payload: dict[str, object] | None = None,
) -> ConversationEvent:
    return ConversationEvent(
        conversation_id=conversation_id,
        event_type="agent_result",
        call_id=call_id,
        capability_code="agent.tender.generate_bid_skeleton",
        sequence=1,
        payload=payload
        or {
            "analysis": {"status": "completed", "summary": "已生成投标骨架"},
            "artifact": {
                "file_name": "投标骨架.docx",
                "media_type": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                "size": 42,
            },
        },
    )


def _harness(
    *,
    events: list[ConversationEvent] | None = None,
    messages: list[Message] | None = None,
    llm_result: ChatLlmResult | Exception | None = None,
    budget: ContextBudget = ContextBudget(max_cost=1_000),
) -> ContinuationHarness:
    conversation_id = (
        messages[0].conversation_id
        if messages
        else events[0].conversation_id
        if events
        else uuid4()
    )
    history = messages or [
        _message(conversation_id, 1, MessageRole.USER, "请生成投标骨架"),
    ]
    writer = FakeConversationWritePort(conversation_id, history)
    event_reader = FakeEventReadPort(
        events if events is not None else [_event(conversation_id)]
    )
    llm = FakeChatLlm(
        llm_result
        or ChatLlmResult(
            content="已根据招标文件生成投标骨架。",
            model="continuation-test",
            prompt_version="dialogue-agent-continuation-v1",
            input_tokens=10,
            output_tokens=8,
            total_tokens=18,
        )
    )
    service = DialogueAgentContinuationService(
        conversation_access=ConversationAccessService(writer),  # type: ignore[arg-type]
        conversation_read=ConversationHistoryReadService(
            FakeConversationReadPort(conversation_id, writer.messages)
        ),
        event_read=event_reader,
        conversation_write=ConversationWriteService(writer),
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=llm,
        context_policy=ContextPolicy(max_messages=20),
        context_budget=budget,
    )
    return ContinuationHarness(service, writer, event_reader, llm, conversation_id)


def _principal() -> RequestPrincipal:
    return RequestPrincipal(subject="user-1", authenticated=True)


def test_continuation_persists_non_empty_answer_with_ordered_history() -> None:
    harness = _harness()

    result = harness.service.execute(
        DialogueAgentContinuationCommand(harness.conversation_id, "call-1", _principal())
    )

    assert result.status == "completed"
    assert result.answer == "已根据招标文件生成投标骨架。"
    assert [message.role for message in harness.writer.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    request = harness.llm.requests[0]
    assert [(message.role.value, message.content) for message in request.history_messages] == [
        ("user", "请生成投标骨架"),
    ]
    assert "已生成投标骨架" in request.user_prompt
    assert request.prompt_version == "dialogue-agent-continuation-v1"


def test_continuation_does_not_call_llm_when_agent_result_is_missing() -> None:
    harness = _harness(events=[])

    result = harness.service.execute(
        DialogueAgentContinuationCommand(harness.conversation_id, "call-1", _principal())
    )

    assert result.status == "unavailable"
    assert result.error_code == "AGENT_RESULT_UNAVAILABLE"
    assert harness.llm.requests == []
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_continuation_rejects_sensitive_result_payload_before_calling_llm() -> None:
    conversation_id = uuid4()
    harness = _harness(
        events=[
            _event(
                conversation_id,
                payload={
                    "analysis": {"summary": "不应传给模型"},
                    "content_base64": "secret-file-content",
                },
            )
        ],
        messages=[_message(conversation_id, 1, MessageRole.USER, "生成文件")],
    )

    result = harness.service.execute(
        DialogueAgentContinuationCommand(conversation_id, "call-1", _principal())
    )

    assert result.status == "unavailable"
    assert result.error_code == "AGENT_RESULT_INVALID"
    assert harness.llm.requests == []
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_continuation_keeps_events_when_model_response_is_empty() -> None:
    harness = _harness(
        llm_result=ChatLlmResult(
            content="  ",
            model="continuation-test",
            prompt_version="dialogue-agent-continuation-v1",
        )
    )

    result = harness.service.execute(
        DialogueAgentContinuationCommand(harness.conversation_id, "call-1", _principal())
    )

    assert result.status == "failed"
    assert result.error_code == "CONTINUATION_EMPTY_RESPONSE"
    assert len(harness.events.events) == 1
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_continuation_keeps_events_when_provider_is_unavailable() -> None:
    harness = _harness(llm_result=RuntimeError("provider unavailable"))

    result = harness.service.execute(
        DialogueAgentContinuationCommand(harness.conversation_id, "call-1", _principal())
    )

    assert result.status == "failed"
    assert result.error_code == "CONTINUATION_LLM_UNAVAILABLE"
    assert len(harness.events.events) == 1
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_continuation_does_not_call_llm_when_context_budget_is_exceeded() -> None:
    harness = _harness(budget=ContextBudget(max_cost=1))

    result = harness.service.execute(
        DialogueAgentContinuationCommand(harness.conversation_id, "call-1", _principal())
    )

    assert result.status == "failed"
    assert result.error_code == "CONTINUATION_CONTEXT_BUDGET_EXCEEDED"
    assert harness.llm.requests == []
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]


def test_continuation_rejects_another_subject_before_reading_or_calling_llm() -> None:
    harness = _harness()

    result = harness.service.execute(
        DialogueAgentContinuationCommand(
            harness.conversation_id,
            "call-1",
            RequestPrincipal(subject="user-2", authenticated=True),
        )
    )

    assert result.status == "unavailable"
    assert result.error_code == "CONVERSATION_ACCESS_DENIED"
    assert harness.events.calls == []
    assert harness.llm.requests == []
    assert [message.role for message in harness.writer.messages] == [MessageRole.USER]
