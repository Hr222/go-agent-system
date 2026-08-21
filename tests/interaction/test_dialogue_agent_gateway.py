from __future__ import annotations

from uuid import uuid4

from app.modules.dialogue.application import (
    DialogueAgentContinuationResult,
    DialogueAgentInvocationResult,
    InMemoryPendingAgentInvocationStore,
)
from app.modules.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
)
from app.modules.interaction.application.gateway import (
    DialogueAgentConfirmationResult,
    GatewayConfirmationCommand,
    GatewayResult,
)
from app.modules.interaction.domain.agent_call import StructuredAgentCall
from app.modules.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
)
from app.modules.security.domain.principal import RequestPrincipal


class PendingAgentGateway:
    def __init__(self) -> None:
        self.proposal = ConfirmationProposal(
            proposal_id="proposal-agent-1",
            capability_code="agent.tender.generate_bid_skeleton",
            capability_type="agent",
            dispatch_key="agent.tender.generate_bid_skeleton",
            inputs={"file_name": "招标文件.docx"},
            summary="生成投标骨架",
            confirmation_prompt="批准后才会执行。",
        )
        self.confirmations: list[GatewayConfirmationCommand] = []

    def recognize(self, command):  # noqa: ANN001
        assert command.user_input == "请生成投标骨架"
        assert command.provided_inputs == {}
        return GatewayResult(
            status="pending",
            message="等待确认",
            proposal=self.proposal,
        )

    def confirm_dialogue_agent(self, command: GatewayConfirmationCommand):
        self.confirmations.append(command)
        if command.action == "cancel":
            return DialogueAgentConfirmationResult(
                status="cancelled",
                message="已取消",
                proposal=self.proposal,
            )
        return DialogueAgentConfirmationResult(
            status="confirmed",
            message="已确认",
            proposal=self.proposal,
            approved_dispatch=ApprovedCapabilityDispatch(
                proposal_id=self.proposal.proposal_id,
                capability_code=self.proposal.capability_code,
                dispatch_key=self.proposal.dispatch_key,
                inputs=dict(self.proposal.inputs),
            ),
        )


class RecordingDialogueInvocation:
    def __init__(self) -> None:
        self.prepare_commands: list[object] = []
        self.invoke_commands: list[object] = []
        self.cancel_calls: list[tuple[object, object]] = []
        self.conversation_id = uuid4()
        self.call = StructuredAgentCall(
            call_id="call-agent-1",
            capability_code="agent.tender.generate_bid_skeleton",
            conversation_id=str(self.conversation_id),
            inputs={"file_name": "招标文件.docx"},
        )

    def prepare_confirmation(self, command):  # noqa: ANN001
        self.prepare_commands.append(command)
        return DialogueAgentInvocationResult(
            status="confirmation_required",
            conversation_id=self.conversation_id,
            call=self.call,
            message="等待确认",
            error_code="CONFIRMATION_REQUIRED",
        )

    def invoke(self, command):  # noqa: ANN001
        self.invoke_commands.append(command)
        return DialogueAgentInvocationResult(
            status="completed",
            conversation_id=self.conversation_id,
            call=self.call,
            message="Agent 已完成执行。",
            output={"artifact": {"file_name": "骨架.docx", "size": 42}},
        )

    def cancel_confirmation(self, *, conversation_id, call, principal):  # noqa: ANN001
        del principal
        self.cancel_calls.append((conversation_id, call))
        return DialogueAgentInvocationResult(
            status="cancelled",
            conversation_id=self.conversation_id,
            call=self.call,
            message="已取消 Agent 调用。",
            error_code="AGENT_CALL_CANCELLED",
        )


class RecordingDialogueContinuation:
    def __init__(self, conversation_id) -> None:  # noqa: ANN001
        self.conversation_id = conversation_id
        self.commands: list[object] = []

    def execute(self, command):  # noqa: ANN001
        self.commands.append(command)
        return DialogueAgentContinuationResult(
            status="completed",
            conversation_id=self.conversation_id,
            call_id="call-agent-1",
            message="已生成最终回复。",
            answer="投标骨架已经生成。",
            model="continuation-test",
            prompt_version="dialogue-agent-continuation-v1",
            input_tokens=10,
            output_tokens=8,
            total_tokens=18,
        )


def _principal() -> RequestPrincipal:
    return RequestPrincipal(
        subject="user-1",
        permissions=frozenset({"agent:tender:execute"}),
        authenticated=True,
    )


def test_chat_agent_confirmation_runs_only_after_gateway_returns_approval() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
    )
    principal = _principal()

    preparation = application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    assert preparation.event is not None
    assert preparation.event.name == "approval_required"
    assert preparation.event.data["conversation_id"] == str(dialogue.conversation_id)
    assert len(dialogue.prepare_commands) == 1
    assert dialogue.invoke_commands == []

    result = application.confirm_agent(
        GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
    )

    assert result is not None
    assert result.status == "completed"
    assert result.execution_result == {"artifact": {"file_name": "骨架.docx", "size": 42}}
    assert len(gateway.confirmations) == 1
    assert len(dialogue.invoke_commands) == 1
    assert dialogue.invoke_commands[0].approved_dispatch is not None
    assert dialogue.invoke_commands[0].persist_call_event is False


def test_chat_agent_confirmation_continues_once_after_single_agent_execution() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    continuation = RecordingDialogueContinuation(dialogue.conversation_id)
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        dialogue_agent_continuation=continuation,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    result = application.confirm_agent(
        GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
    )

    assert result is not None
    assert result.status == "completed"
    assert result.execution_result == {
        "answer": "投标骨架已经生成。",
        "agent_result": {"artifact": {"file_name": "骨架.docx", "size": 42}},
        "model": "continuation-test",
        "prompt_version": "dialogue-agent-continuation-v1",
        "usage": {"input_tokens": 10, "output_tokens": 8, "total_tokens": 18},
    }
    assert len(dialogue.invoke_commands) == 1
    assert len(continuation.commands) == 1


def test_chat_agent_cancellation_records_terminal_event_without_invocation() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    result = application.confirm_agent(
        GatewayConfirmationCommand("proposal-agent-1", "cancel", principal)
    )

    assert result is not None
    assert result.status == "cancelled"
    assert len(dialogue.cancel_calls) == 1
    assert dialogue.invoke_commands == []
