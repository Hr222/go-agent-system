from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.modules.conversation.domain import Conversation, ConversationEvent
from app.modules.dialogue.application import (
    AgentResultProjector,
    DialogueAgentInvocationCommand,
    DialogueAgentInvocationService,
)
from app.modules.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatchResult,
)
from app.modules.interaction.domain.agent_call import AgentCallResult, StructuredAgentCall
from app.modules.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.modules.security.domain.principal import RequestPrincipal


@dataclass
class FakeRead:
    conversations: set = field(default_factory=set)

    def read_history(self, *, conversation_id, limit, after_sequence):  # noqa: ANN001, ARG002
        if conversation_id not in self.conversations:
            from app.modules.conversation.errors import ConversationNotFoundError

            raise ConversationNotFoundError("missing")
        return object()


@dataclass
class FakeWrite:
    conversations: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations[conversation.id] = conversation
        return conversation

    def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
        self.messages.append((conversation_id, role, content))
        return object()


@dataclass
class FakeEvents:
    events: list[ConversationEvent] = field(default_factory=list)

    def next_event_sequence(self, *, conversation_id):  # noqa: ANN001
        return 1 + max(
            (event.sequence for event in self.events if event.conversation_id == conversation_id),
            default=0,
        )

    def save_event(self, event: ConversationEvent) -> ConversationEvent:
        self.events.append(event)
        return event


@dataclass
class FakeDispatcher:
    result: AgentCallDispatchResult
    calls: list[AgentCallDispatchCommand] = field(default_factory=list)

    def dispatch(self, command: AgentCallDispatchCommand) -> AgentCallDispatchResult:
        self.calls.append(command)
        return self.result


def _principal() -> RequestPrincipal:
    return RequestPrincipal(subject="user-1", authenticated=True)


def _service(dispatch_result: AgentCallDispatchResult):
    write = FakeWrite()
    conversation = write.save_conversation(Conversation())
    read = FakeRead({conversation.id})
    events = FakeEvents()
    dispatcher = FakeDispatcher(dispatch_result)
    service = DialogueAgentInvocationService(
        conversation_read=read,
        conversation_write=write,
        event_write=events,
        dispatcher=dispatcher,  # type: ignore[arg-type]
        projector=AgentResultProjector(),
    )
    return service, conversation, write, events, dispatcher


def _call(conversation_id: str) -> StructuredAgentCall:
    return StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        conversation_id=conversation_id,
        inputs={"file_name": "招标.docx"},
    )


def test_projector_keeps_tender_metadata_and_drops_binary_and_provider_details() -> None:
    projected = AgentResultProjector().project(
        {
            "analysis": {"summary": "完成", "status": "completed", "provider": "secret"},
            "artifacts": [
                {
                    "file_name": "骨架.docx",
                    "media_type": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ),
                    "content": {"__agent_bytes__": True, "size": 42, "base64": "secret"},
                    "provider_response": {"token": "secret"},
                }
            ],
        },
        call_id="call-1",
    )

    assert projected["analysis"] == {"status": "completed", "summary": "完成"}
    assert projected["artifacts"][0]["file_name"] == "骨架.docx"  # type: ignore[index]
    assert "content" not in projected["artifacts"][0]  # type: ignore[operator]
    assert "provider_response" not in projected["artifacts"][0]  # type: ignore[operator]


def test_conversation_event_rejects_non_json_payload() -> None:
    import pytest

    with pytest.raises(ValueError, match="JSON"):
        ConversationEvent(
            conversation_id=uuid4(),
            event_type="agent_result",
            call_id="call-1",
            capability_code="agent.tender.generate_bid_skeleton",
            sequence=1,
            payload={"content": b"raw-binary"},
        )


def test_invocation_writes_call_and_result_without_assistant_message() -> None:
    call = _call(str(uuid4()))
    result = AgentCallDispatchResult(
        status="completed",
        call=call,
        result=AgentCallResult(
            **call.model_dump(exclude={"inputs"}),
            output={"answer": "完成"},
        ),
    )
    service, conversation, write, events, dispatcher = _service(result)
    call = _call(str(conversation.id))
    result = AgentCallDispatchResult(
        status="completed",
        call=call,
        result=AgentCallResult(
            **call.model_dump(exclude={"inputs"}),
            output={"answer": "完成"},
        ),
    )
    dispatcher.result = result
    response = service.invoke(
        DialogueAgentInvocationCommand(
            conversation_id=conversation.id,
            capability_code=call.capability_code,
            inputs=dict(call.inputs),
            principal=_principal(),
            user_input="生成招标骨架",
            call=call,
        )
    )

    assert response.status == "completed"
    assert [event.event_type for event in events.events] == ["agent_call", "agent_result"]
    assert write.messages == [(conversation.id, "user", "生成招标骨架")]
    assert len(dispatcher.calls) == 1


def test_confirmation_required_does_not_execute_and_returns_controlled_state() -> None:
    call = _call(str(uuid4()))
    result = AgentCallDispatchResult(
        status="confirmation_required",
        call=call,
        error=None,
    )
    service, conversation, _write, events, dispatcher = _service(result)
    call = _call(str(conversation.id))
    dispatcher.result = AgentCallDispatchResult(status="confirmation_required", call=call)
    response = service.invoke(
        DialogueAgentInvocationCommand(
            conversation_id=conversation.id,
            capability_code=call.capability_code,
            inputs=dict(call.inputs),
            principal=_principal(),
            call=call,
        )
    )

    assert response.status == "confirmation_required"
    assert dispatcher.calls
    assert [event.event_type for event in events.events] == ["agent_call"]


def test_prepare_confirmation_does_not_invoke_dispatcher_and_cancel_is_persisted() -> None:
    call = _call(str(uuid4()))
    service, conversation, _write, events, dispatcher = _service(
        AgentCallDispatchResult(status="confirmation_required", call=call)
    )
    pending = service.prepare_confirmation(
        DialogueAgentInvocationCommand(
            conversation_id=conversation.id,
            capability_code=call.capability_code,
            inputs=dict(call.inputs),
            principal=_principal(),
            user_input="生成招标骨架",
        )
    )
    cancelled = service.cancel_confirmation(
        conversation_id=conversation.id,
        call=pending.call,
    )

    assert dispatcher.calls == []
    assert cancelled.status == "cancelled"
    assert [event.event_type for event in events.events] == ["agent_call", "agent_error"]
    assert events.events[-1].payload["error_code"] == "AGENT_CALL_CANCELLED"


def test_invocation_rejects_cross_conversation_call() -> None:
    call = _call(str(uuid4()))
    result = AgentCallDispatchResult(status="failed", call=call)
    service, conversation, _write, _events, _dispatcher = _service(result)

    import pytest

    with pytest.raises(ValueError, match="跨会话"):
        service.invoke(
            DialogueAgentInvocationCommand(
                conversation_id=conversation.id,
                capability_code=call.capability_code,
                inputs=dict(call.inputs),
                principal=_principal(),
                approved_dispatch=ApprovedCapabilityDispatch(
                    proposal_id="p",
                    capability_code=call.capability_code,
                    dispatch_key="agent.tender.generate_bid_skeleton",
                    inputs=dict(call.inputs),
                ),
                call=call,
            )
        )


def test_invocation_creates_conversation_when_the_request_has_none() -> None:
    call = _call(str(uuid4()))
    result = AgentCallDispatchResult(
        status="completed",
        call=call,
        result=AgentCallResult(
            **call.model_dump(exclude={"inputs"}),
            output={"answer": "完成"},
        ),
    )
    write = FakeWrite()
    events = FakeEvents()
    dispatcher = FakeDispatcher(result)
    service = DialogueAgentInvocationService(
        conversation_read=FakeRead(),
        conversation_write=write,
        event_write=events,
        dispatcher=dispatcher,  # type: ignore[arg-type]
        projector=AgentResultProjector(),
    )

    response = service.invoke(
        DialogueAgentInvocationCommand(
            conversation_id=None,
            capability_code=call.capability_code,
            inputs=dict(call.inputs),
            principal=_principal(),
        )
    )

    assert response.conversation_id in write.conversations
    assert response.call.conversation_id == str(response.conversation_id)
    assert [event.event_type for event in events.events] == ["agent_call", "agent_result"]
