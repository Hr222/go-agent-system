from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from app.modules.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationResolveQuery,
)
from app.modules.conversation.domain import ConversationEvent, MessageRole
from app.modules.conversation.ports import (
    ConversationEventWritePort,
    ConversationWritePort,
)
from app.modules.dialogue.application.agent_result_projection import AgentResultProjector
from app.modules.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatcher,
    AgentCallDispatchResult,
)
from app.modules.interaction.domain.agent_call import StructuredAgentCall
from app.modules.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.modules.security.domain.principal import RequestPrincipal

InvocationStatus = Literal[
    "completed",
    "confirmation_required",
    "cancelled",
    "rejected",
    "unavailable",
    "failed",
]


@dataclass(frozen=True, slots=True)
class DialogueAgentInvocationCommand:
    conversation_id: UUID | None
    capability_code: str
    inputs: dict[str, object]
    principal: RequestPrincipal
    user_input: str | None = None
    approved_dispatch: ApprovedCapabilityDispatch | None = None
    call: StructuredAgentCall | None = None
    persist_call_event: bool = True


@dataclass(frozen=True, slots=True)
class DialogueAgentInvocationResult:
    status: InvocationStatus
    conversation_id: UUID
    call: StructuredAgentCall
    message: str
    output: dict[str, object] | None = None
    error_code: str | None = None


class DialogueAgentInvocationService:
    """在 Conversation 中执行一次已授权 Agent 调用。"""

    def __init__(
        self,
        *,
        conversation_access: ConversationAccessService,
        conversation_write: ConversationWritePort,
        event_write: ConversationEventWritePort,
        dispatcher: AgentCallDispatcher,
        projector: AgentResultProjector,
    ) -> None:
        self._conversation_access = conversation_access
        self._conversation_write = conversation_write
        self._event_write = event_write
        self._dispatcher = dispatcher
        self._projector = projector

    def invoke(self, command: DialogueAgentInvocationCommand) -> DialogueAgentInvocationResult:
        conversation_id = self._ensure_conversation(
            command.conversation_id,
            principal=command.principal,
        )
        call = command.call or self._new_call(command, conversation_id)
        if call.conversation_id != str(conversation_id):
            raise ValueError("Agent 调用不能跨会话执行。")
        if command.user_input is not None:
            self._conversation_write.append_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=command.user_input,
            )
        dispatched = self._dispatcher.dispatch(
            AgentCallDispatchCommand(
                call=call,
                principal=command.principal,
                approved_dispatch=command.approved_dispatch,
            )
        )
        if command.persist_call_event:
            self._append_event(
                conversation_id=conversation_id,
                call=call,
                event_type="agent_call",
                payload={
                    "status": dispatched.status,
                    "input_fields": sorted(call.inputs),
                },
            )
        return self._finish(conversation_id, call, dispatched)

    def prepare_confirmation(
        self,
        command: DialogueAgentInvocationCommand,
    ) -> DialogueAgentInvocationResult:
        """持久化待确认调用，但在用户确认前绝不触发 Agent Dispatcher。"""

        conversation_id = self._ensure_conversation(
            command.conversation_id,
            principal=command.principal,
        )
        call = self._new_call(command, conversation_id)
        if command.user_input is not None:
            self._conversation_write.append_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=command.user_input,
            )
        self._append_event(
            conversation_id=conversation_id,
            call=call,
            event_type="agent_call",
            payload={
                "status": "confirmation_required",
                "input_fields": sorted(call.inputs),
            },
        )
        return DialogueAgentInvocationResult(
            status="confirmation_required",
            conversation_id=conversation_id,
            call=call,
            message="该 Agent 调用需要明确确认后才会执行。",
            error_code="CONFIRMATION_REQUIRED",
        )

    def cancel_confirmation(
        self,
        *,
        conversation_id: UUID,
        call: StructuredAgentCall,
        principal: RequestPrincipal,
    ) -> DialogueAgentInvocationResult:
        """以受控事件记录用户取消，避免留下无终态的调用记录。"""

        self._ensure_conversation(conversation_id, principal=principal)

        self._append_event(
            conversation_id=conversation_id,
            call=call,
            event_type="agent_error",
            payload={
                "error_code": "AGENT_CALL_CANCELLED",
                "message": "用户取消了 Agent 调用。",
                "retryable": False,
            },
        )
        return DialogueAgentInvocationResult(
            status="cancelled",
            conversation_id=conversation_id,
            call=call,
            message="已取消 Agent 调用，未执行任何业务操作。",
            error_code="AGENT_CALL_CANCELLED",
        )

    @staticmethod
    def _new_call(
        command: DialogueAgentInvocationCommand,
        conversation_id: UUID,
    ) -> StructuredAgentCall:
        return StructuredAgentCall(
            call_id=uuid4().hex,
            capability_code=command.capability_code,
            conversation_id=str(conversation_id),
            turn_id=uuid4().hex,
            run_id=uuid4().hex,
            inputs=dict(command.inputs),
        )

    def _ensure_conversation(
        self,
        conversation_id: UUID | None,
        *,
        principal: RequestPrincipal,
    ) -> UUID:
        if conversation_id is None:
            return self._conversation_access.create(
                ConversationCreateCommand(principal=principal)
            ).id
        if not isinstance(conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        self._conversation_access.resolve(
            ConversationResolveQuery(
                principal=principal,
                conversation_id=conversation_id,
            )
        )
        return conversation_id

    def _finish(
        self,
        conversation_id: UUID,
        call: StructuredAgentCall,
        dispatched: AgentCallDispatchResult,
    ) -> DialogueAgentInvocationResult:
        if dispatched.status == "completed" and dispatched.result is not None:
            output = self._projector.project(dispatched.result.output, call_id=call.call_id)
            self._append_event(
                conversation_id=conversation_id,
                call=call,
                event_type="agent_result",
                payload=output,
            )
            return DialogueAgentInvocationResult(
                status="completed",
                conversation_id=conversation_id,
                call=call,
                message="Agent 已完成执行。",
                output=output,
            )

        error = dispatched.error
        if dispatched.status == "confirmation_required":
            return DialogueAgentInvocationResult(
                status="confirmation_required",
                conversation_id=conversation_id,
                call=call,
                message="该 Agent 调用需要明确确认后才会执行。",
                error_code=error.error_code if error else "CONFIRMATION_REQUIRED",
            )

        error_code = error.error_code if error else "AGENT_CALL_FAILED"
        message = error.message if error else "Agent 调用未完成。"
        self._append_event(
            conversation_id=conversation_id,
            call=call,
            event_type="agent_error",
            payload={
                "error_code": error_code,
                "message": message,
                "retryable": bool(error.retryable) if error else False,
            },
        )
        return DialogueAgentInvocationResult(
            status=dispatched.status,
            conversation_id=conversation_id,
            call=call,
            message=message,
            error_code=error_code,
        )

    def _append_event(
        self,
        *,
        conversation_id: UUID,
        call: StructuredAgentCall,
        event_type: Literal["agent_call", "agent_result", "agent_error"],
        payload: dict[str, object],
    ) -> None:
        sequence = self._event_write.next_event_sequence(conversation_id=conversation_id)
        self._event_write.save_event(
            ConversationEvent(
                conversation_id=conversation_id,
                event_type=event_type,
                call_id=call.call_id,
                capability_code=call.capability_code,
                sequence=sequence,
                payload=payload,
            )
        )


__all__ = [
    "DialogueAgentInvocationCommand",
    "DialogueAgentInvocationResult",
    "DialogueAgentInvocationService",
]
