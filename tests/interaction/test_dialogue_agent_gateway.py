from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.platform.dialogue.application import (
    ConversationTurnCoordinator,
    DialogueAgentContinuationResult,
    DialogueAgentInvocationResult,
    DialogueAgentTurnExecutor,
    DialogueAgentTurnWorker,
    InMemoryPendingAgentInvocationStore,
)
from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
)
from app.platform.interaction.application.gateway import (
    DialogueAgentConfirmationResult,
    GatewayConfirmationCommand,
    GatewayResult,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
)
from app.platform.security.domain.principal import RequestPrincipal


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


class RejectedAgentGateway(PendingAgentGateway):
    def confirm_dialogue_agent(self, command: GatewayConfirmationCommand):
        self.confirmations.append(command)
        return DialogueAgentConfirmationResult(
            status="rejected",
            message="能力目录已变更。",
            proposal=self.proposal,
            error_code="CAPABILITY_UNAVAILABLE",
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


class FailingDialogueContinuation(RecordingDialogueContinuation):
    def execute(self, command):  # noqa: ANN001
        self.commands.append(command)
        return DialogueAgentContinuationResult(
            status="failed",
            conversation_id=self.conversation_id,
            call_id="call-agent-1",
            message="最终回复暂时无法生成。",
            error_code="CONTINUATION_LLM_UNAVAILABLE",
        )


class CoordinatorAwareStreamingRuntime:
    def __init__(self, coordinator, conversation_id) -> None:  # noqa: ANN001
        self.coordinator = coordinator
        self.conversation_id = conversation_id
        self.commands: list[object] = []

    async def execute(self, command):  # noqa: ANN001
        lease = await self.coordinator.acquire(self.conversation_id)
        self.commands.append(command)

        async def stream():
            try:
                yield type("Event", (), {"kind": "started"})()
            finally:
                lease.release()

        return stream()


class RecordingAgentTurnWorkerFactory:
    def __init__(self, invocation, continuation=None) -> None:  # noqa: ANN001
        self.invocation = invocation
        self.continuation = continuation
        self.created = 0

    def create(self):  # noqa: ANN201
        self.created += 1
        return DialogueAgentTurnWorker(
            invocation=self.invocation,
            continuation=self.continuation,
        )


class FailIfCreatedAgentTurnWorkerFactory:
    def __init__(self) -> None:
        self.created = 0

    def create(self):  # noqa: ANN201
        self.created += 1
        raise AssertionError("确认复核拒绝时不得创建 Agent worker。")


def _turn_executor(
    invocation,  # noqa: ANN001
    continuation=None,  # noqa: ANN001
    coordinator: ConversationTurnCoordinator | None = None,
) -> DialogueAgentTurnExecutor:
    return DialogueAgentTurnExecutor(
        coordinator=coordinator or ConversationTurnCoordinator(),
        worker_factory=RecordingAgentTurnWorkerFactory(invocation, continuation),
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
        dialogue_agent_turn_executor=_turn_executor(dialogue),
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

    result = asyncio.run(
        application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )
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
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue, continuation),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    result = asyncio.run(
        application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )
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


def test_gateway_rejection_after_proposal_consumption_clears_pending_without_worker() -> None:
    gateway = RejectedAgentGateway()
    dialogue = RecordingDialogueInvocation()
    pending = InMemoryPendingAgentInvocationStore()
    factory = FailIfCreatedAgentTurnWorkerFactory()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=pending,
        dialogue_agent_turn_executor=DialogueAgentTurnExecutor(
            coordinator=ConversationTurnCoordinator(),
            worker_factory=factory,
        ),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    result = asyncio.run(
        application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )
    )

    assert result is not None
    assert result.status == "rejected"
    assert result.error_code == "CAPABILITY_UNAVAILABLE"
    assert factory.created == 0
    assert dialogue.invoke_commands == []
    assert pending.read(proposal_id="proposal-agent-1", subject=principal.subject) is None


def test_confirm_agent_waits_on_shared_conversation_lease_before_consuming_state() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    continuation = RecordingDialogueContinuation(dialogue.conversation_id)
    coordinator = ConversationTurnCoordinator()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        CoordinatorAwareStreamingRuntime(coordinator, dialogue.conversation_id),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue, continuation, coordinator),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    async def scenario() -> None:
        holder = await coordinator.acquire(dialogue.conversation_id)
        confirmation = asyncio.create_task(
            application.confirm_agent(
                GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
            )
        )
        await asyncio.sleep(0)

        assert not confirmation.done()
        assert gateway.confirmations == []
        assert dialogue.invoke_commands == []
        assert continuation.commands == []

        confirmation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await confirmation
        holder.release()

        retried = await application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )
        assert retried is not None
        assert retried.status == "completed"

    asyncio.run(scenario())

    assert len(dialogue.invoke_commands) == 1
    assert len(continuation.commands) == 1
    assert coordinator.tracked_conversation_count == 0


def test_confirmed_agent_and_chat_use_the_same_conversation_lease() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    coordinator = ConversationTurnCoordinator()
    chat = CoordinatorAwareStreamingRuntime(coordinator, dialogue.conversation_id)
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        chat,  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue, coordinator=coordinator),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    async def scenario() -> None:
        holder = await coordinator.acquire(dialogue.conversation_id)
        confirmation = asyncio.create_task(
            application.confirm_agent(
                GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
            )
        )
        chat_task = asyncio.create_task(
            chat.execute(type("Command", (), {})())
        )
        await asyncio.sleep(0)

        assert not confirmation.done()
        assert not chat_task.done()
        assert chat.commands == []

        holder.release()
        result, stream = await asyncio.gather(confirmation, chat_task)
        assert result is not None
        assert result.status == "completed"
        assert len(dialogue.invoke_commands) == 1
        assert len(chat.commands) == 1
        await anext(stream)
        await stream.aclose()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_concurrent_confirmation_consumes_pending_invocation_only_once() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    coordinator = ConversationTurnCoordinator()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue, coordinator=coordinator),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    async def scenario():
        return await asyncio.gather(
            application.confirm_agent(
                GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
            ),
            application.confirm_agent(
                GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
            ),
        )

    results = asyncio.run(scenario())

    assert sum(result is not None and result.status == "completed" for result in results) == 1
    assert sum(
        result is None or (result is not None and result.status == "rejected")
        for result in results
    ) == 1
    assert len(dialogue.invoke_commands) == 1
    assert coordinator.tracked_conversation_count == 0


def test_continuation_failure_releases_conversation_lease() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    coordinator = ConversationTurnCoordinator()
    continuation = FailingDialogueContinuation(dialogue.conversation_id)
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue, continuation, coordinator),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    async def scenario() -> None:
        result = await application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )
        assert result is not None
        assert result.status == "failed"

        next_lease = await coordinator.acquire(dialogue.conversation_id)
        next_lease.release()

    asyncio.run(scenario())

    assert len(dialogue.invoke_commands) == 1
    assert len(continuation.commands) == 1
    assert coordinator.tracked_conversation_count == 0


def test_confirmed_agents_in_different_conversations_do_not_wait_for_each_other() -> None:
    coordinator = ConversationTurnCoordinator()
    principal = _principal()
    first_gateway = PendingAgentGateway()
    first_dialogue = RecordingDialogueInvocation()
    second_gateway = PendingAgentGateway()
    second_dialogue = RecordingDialogueInvocation()
    first = InteractionChatStreamApplication(
        first_gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=first_dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(first_dialogue, coordinator=coordinator),
    )
    second = InteractionChatStreamApplication(
        second_gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=second_dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(second_dialogue, coordinator=coordinator),
    )
    first.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )
    second.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    async def scenario() -> None:
        first_lease = await coordinator.acquire(first_dialogue.conversation_id)
        second_result = await second.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "confirm", principal)
        )

        assert second_result is not None
        assert second_result.status == "completed"
        assert first_dialogue.invoke_commands == []
        first_lease.release()

    asyncio.run(scenario())

    assert len(second_dialogue.invoke_commands) == 1
    assert coordinator.tracked_conversation_count == 0


def test_chat_agent_cancellation_records_terminal_event_without_invocation() -> None:
    gateway = PendingAgentGateway()
    dialogue = RecordingDialogueInvocation()
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        dialogue_agent_invocation=dialogue,  # type: ignore[arg-type]
        pending_agent_invocations=InMemoryPendingAgentInvocationStore(),
        dialogue_agent_turn_executor=_turn_executor(dialogue),
    )
    principal = _principal()
    application.prepare(
        InteractionChatStreamCommand(
            user_input="请生成投标骨架",
            principal=principal,
            provided_inputs={},
        )
    )

    result = asyncio.run(
        application.confirm_agent(
            GatewayConfirmationCommand("proposal-agent-1", "cancel", principal)
        )
    )

    assert result is not None
    assert result.status == "cancelled"
    assert len(dialogue.cancel_calls) == 1
    assert dialogue.invoke_commands == []
