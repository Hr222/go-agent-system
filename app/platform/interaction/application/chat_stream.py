from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from app.platform.conversation.errors import ConversationAccessDeniedError
from app.platform.interaction.application.gateway import (
    DirectCapabilityExecution,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
    IntentInteractionGateway,
)
from app.platform.interaction.ports.chat_preparation import InteractionChatPreparationPort
from app.platform.security.domain.principal import RequestPrincipal
from app.shared.async_task import run_sync_protected
from app.shared.config import settings

if TYPE_CHECKING:
    from app.platform.dialogue.application import (
        DialogueAgentInvocationService,
        InMemoryPendingAgentInvocationStore,
        PendingAgentInvocation,
        StreamingConversationEvent,
        StreamingConversationRuntime,
    )
    from app.platform.dialogue.application.agent_turn import (
        DialogueAgentTurnExecutor,
        DialogueAgentTurnPreparation,
        DialogueAgentTurnResult,
    )

InteractionStreamEventName = Literal[
    "meta",
    "delta",
    "complete",
    "approval_required",
    "result",
    "error",
    "heartbeat",
]
DisconnectChecker = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class InteractionChatStreamCommand:
    user_input: str
    principal: RequestPrincipal
    provided_inputs: dict[str, object]
    conversation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class InteractionStreamEvent:
    name: InteractionStreamEventName
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class InteractionStreamPreparation:
    """A safe routing result prepared before an SSE response starts."""

    kind: Literal["chat", "single_event"]
    event: InteractionStreamEvent | None = None
    direct_execution: DirectCapabilityExecution | None = None
    principal: RequestPrincipal | None = None
    conversation_id: UUID | None = None


class InteractionChatStreamApplication:
    """Route a chat request on the server, then emit controlled interaction events."""

    def __init__(
        self,
        gateway: IntentInteractionGateway | None,
        streaming_conversation: StreamingConversationRuntime,
        dialogue_agent_invocation: DialogueAgentInvocationService | None = None,
        pending_agent_invocations: InMemoryPendingAgentInvocationStore | None = None,
        dialogue_agent_turn_executor: DialogueAgentTurnExecutor | None = None,
        preparation: InteractionChatPreparationPort | None = None,
    ) -> None:
        self._gateway = gateway
        self._streaming_conversation = streaming_conversation
        self._dialogue_agent_invocation = dialogue_agent_invocation
        self._pending_agent_invocations = pending_agent_invocations
        self._dialogue_agent_turn_executor = dialogue_agent_turn_executor
        self._preparation = preparation

    def prepare(
        self,
        command: InteractionChatStreamCommand,
    ) -> InteractionStreamPreparation:
        """Complete routing before model execution or an SSE response begins."""

        if self._gateway is None:
            raise RuntimeError("同步交互 Gateway 未配置。")

        try:
            result = self._gateway.recognize(
                GatewayRecognitionCommand(
                    user_input=command.user_input,
                    principal=command.principal,
                    provided_inputs=dict(command.provided_inputs),
                    conversation_id=command.conversation_id,
                )
            )
        except ConversationAccessDeniedError:
            return _single_error("CONVERSATION_ACCESS_DENIED", "会话不可用。")
        except Exception:  # noqa: BLE001 - never expose interaction internals
            return _single_error("INTERACTION_UNAVAILABLE", "请求暂时无法处理。")

        if _is_pending_agent(result) and self._can_prepare_agent_confirmation():
            return self._prepare_agent_confirmation(command, result)

        if result.status != "authorized":
            return InteractionStreamPreparation(
                kind="single_event",
                event=_result_event(result),
            )

        direct_execution = result.direct_execution
        if not _is_general_chat_execution(direct_execution):
            return _single_error(
                "UNSUPPORTED_UNCONFIRMED_CAPABILITY",
                "该请求暂时无法通过当前对话通道处理。",
            )
        return InteractionStreamPreparation(
            kind="chat",
            direct_execution=direct_execution,
            principal=command.principal,
            conversation_id=command.conversation_id,
        )

    async def prepare_async(
        self,
        command: InteractionChatStreamCommand,
    ) -> InteractionStreamPreparation:
        """异步流式入口使用的准备边界；兼容注入的同步测试替身。"""

        if self._preparation is not None:
            return await self._preparation.prepare(command)
        return self.prepare(command)

    def cancel_preparation(
        self,
        command: InteractionChatStreamCommand,
        preparation: InteractionStreamPreparation,
    ) -> None:
        """收口尚未发出批准事件的 Agent 准备结果。"""

        if preparation.event is None or preparation.event.name != "approval_required":
            return
        proposal_id = preparation.event.data.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id:
            raise ValueError("Agent 批准提议标识无效。")
        pending = self._pending_agent_invocations
        if pending is None or self._dialogue_agent_invocation is None:
            return
        self._cancel_agent_confirmation(
            GatewayConfirmationCommand(
                proposal_id=proposal_id,
                action="cancel",
                principal=command.principal,
            )
        )

    async def confirm_agent(
        self,
        command: GatewayConfirmationCommand,
    ) -> GatewayResult | None:
        """确认已由 Chat 绑定的 Agent 调用；None 交由既有非 Agent 路径处理。"""

        if self._pending_agent_invocations is None or self._dialogue_agent_invocation is None:
            return None
        pending = self._pending_agent_invocations.read(
            proposal_id=command.proposal_id,
            subject=command.principal.subject,
        )
        if pending is None:
            return None

        if command.action == "cancel":
            return await run_sync_protected(lambda: self._cancel_agent_confirmation(command))
        if self._dialogue_agent_turn_executor is None:
            return GatewayResult(
                status="failed",
                message="对话 Agent 调用暂时不可用。",
                error_code="DIALOGUE_AGENT_UNAVAILABLE",
            )
        conversation_id = pending.command.conversation_id
        if conversation_id is None:
            return GatewayResult(
                status="rejected",
                message="对话 Agent 调用上下文不可用。",
                error_code="DIALOGUE_AGENT_CONTEXT_UNAVAILABLE",
            )

        # 锁等待期间不运行此确认操作，取消请求因而不会消费一次性状态。
        from app.platform.dialogue.application.agent_turn import DialogueAgentTurnRequest

        result = await self._dialogue_agent_turn_executor.execute(
            DialogueAgentTurnRequest(
                conversation_id=conversation_id,
                confirm=lambda: self._confirm_agent_in_turn(command, pending),
            )
        )
        return _gateway_result_from_agent_turn(result)

    def _confirm_agent_in_turn(
        self,
        command: GatewayConfirmationCommand,
        pending: PendingAgentInvocation,
    ) -> DialogueAgentTurnPreparation:
        """在 Dialogue 租约内保留 Gateway 的确认与授权控制面职责。"""

        from app.platform.dialogue.application.agent_turn import (
            DialogueAgentTurnCommand,
            DialogueAgentTurnPreparation,
            DialogueAgentTurnResult,
        )

        with self._pending_agent_invocations.transaction():
            try:
                confirmation = self._gateway.confirm_dialogue_agent(command)
            except BaseException:
                # Gateway 可能已经消费 proposal；此时 pending 不能遗留到 TTL。
                self._pending_agent_invocations.consume(
                    proposal_id=command.proposal_id,
                    subject=command.principal.subject,
                )
                raise

            # proposal 一旦进入终态，matching pending invocation 必须同步收口。
            consumed = self._pending_agent_invocations.consume(
                proposal_id=command.proposal_id,
                subject=command.principal.subject,
            )
            if confirmation.status == "rejected":
                return DialogueAgentTurnPreparation(
                    result=DialogueAgentTurnResult(
                        status="rejected",
                        message=confirmation.message,
                        error_code=confirmation.error_code,
                        conversation_id=pending.command.conversation_id,
                    )
                )
            if (
                consumed is None
                or consumed.command.conversation_id is None
                or consumed.command.call is None
            ):
                return DialogueAgentTurnPreparation(
                    result=DialogueAgentTurnResult(
                        status="rejected",
                        message="对话 Agent 调用上下文不可用。",
                        error_code="DIALOGUE_AGENT_CONTEXT_UNAVAILABLE",
                    )
                )
            if confirmation.approved_dispatch is None:
                return DialogueAgentTurnPreparation(
                    result=DialogueAgentTurnResult(
                        status="rejected",
                        message="确认提议未生成有效批准信息。",
                        error_code="APPROVED_DISPATCH_UNAVAILABLE",
                        conversation_id=consumed.command.conversation_id,
                    )
                )

            return DialogueAgentTurnPreparation(
                command=DialogueAgentTurnCommand(
                    conversation_id=consumed.command.conversation_id,
                    capability_code=consumed.command.capability_code,
                    inputs=dict(consumed.command.inputs),
                    principal=command.principal,
                    approved_dispatch=confirmation.approved_dispatch,
                    call=consumed.command.call,
                )
            )

    def _cancel_agent_confirmation(
        self,
        command: GatewayConfirmationCommand,
    ) -> GatewayResult:
        """取消不执行 Agent，沿用既有短路径但始终清理一次性状态。"""

        with self._pending_agent_invocations.transaction():
            current = self._pending_agent_invocations.read(
                proposal_id=command.proposal_id,
                subject=command.principal.subject,
            )
            if current is None:
                return GatewayResult(
                    status="rejected",
                    message="确认提议不存在、已过期、已处理或不属于当前主体。",
                    error_code="PROPOSAL_UNAVAILABLE",
                )
            try:
                confirmation = self._gateway.confirm_dialogue_agent(command)
            except BaseException:
                self._pending_agent_invocations.consume(
                    proposal_id=command.proposal_id,
                    subject=command.principal.subject,
                )
                raise

            consumed = self._pending_agent_invocations.consume(
                proposal_id=command.proposal_id,
                subject=command.principal.subject,
            )
            if confirmation.status == "rejected":
                return GatewayResult(
                    status="rejected",
                    message=confirmation.message,
                    error_code=confirmation.error_code,
                    conversation_id=current.command.conversation_id,
                )
            if (
                consumed is None
                or consumed.command.conversation_id is None
                or consumed.command.call is None
            ):
                return GatewayResult(
                    status="rejected",
                    message="对话 Agent 调用上下文不可用。",
                    error_code="DIALOGUE_AGENT_CONTEXT_UNAVAILABLE",
                )
            if confirmation.status != "cancelled":
                return GatewayResult(
                    status="rejected",
                    message="确认提议未生成有效取消信息。",
                    error_code="CANCELLATION_UNAVAILABLE",
                    conversation_id=consumed.command.conversation_id,
                )
            try:
                result = self._dialogue_agent_invocation.cancel_confirmation(
                    conversation_id=consumed.command.conversation_id,
                    call=consumed.command.call,
                    principal=command.principal,
                )
            except ConversationAccessDeniedError:
                return _conversation_access_denied_result()
            return GatewayResult(
                status=result.status,
                message=result.message,
                error_code=result.error_code,
                conversation_id=result.conversation_id,
            )

    def _can_prepare_agent_confirmation(self) -> bool:
        return (
            self._dialogue_agent_invocation is not None
            and self._pending_agent_invocations is not None
        )

    def _prepare_agent_confirmation(
        self,
        command: InteractionChatStreamCommand,
        gateway_result: GatewayResult,
    ) -> InteractionStreamPreparation:
        proposal = gateway_result.proposal
        assert proposal is not None
        assert self._dialogue_agent_invocation is not None
        assert self._pending_agent_invocations is not None
        from app.platform.dialogue.application import DialogueAgentInvocationCommand
        try:
            result = self._dialogue_agent_invocation.prepare_confirmation(
                DialogueAgentInvocationCommand(
                    conversation_id=command.conversation_id,
                    capability_code=proposal.capability_code,
                    inputs=dict(proposal.inputs),
                    principal=command.principal,
                    user_input=command.user_input,
                )
            )
            self._pending_agent_invocations.save(
                proposal_id=proposal.proposal_id,
                command=DialogueAgentInvocationCommand(
                    conversation_id=result.conversation_id,
                    capability_code=proposal.capability_code,
                    inputs=dict(proposal.inputs),
                    principal=command.principal,
                    call=result.call,
                ),
            )
        except ConversationAccessDeniedError:
            return _single_error("CONVERSATION_ACCESS_DENIED", "会话不可用。")
        except ValueError as exc:
            return _single_error("DIALOGUE_AGENT_INPUT_INVALID", str(exc))
        except Exception:  # noqa: BLE001 - database and invocation internals stay server-side
            return _single_error("DIALOGUE_AGENT_UNAVAILABLE", "对话 Agent 调用暂时不可用。")

        return InteractionStreamPreparation(
            kind="single_event",
            event=InteractionStreamEvent(
                "approval_required",
                {
                    "proposal_id": proposal.proposal_id,
                    "state": proposal.state,
                    "summary": proposal.summary,
                    "confirmation_prompt": proposal.confirmation_prompt,
                    "conversation_id": str(result.conversation_id),
                },
            ),
        )

    async def stream(
        self,
        preparation: InteractionStreamPreparation,
        *,
        is_disconnected: DisconnectChecker,
    ) -> AsyncIterator[InteractionStreamEvent]:
        """Emit the selected controlled response without leaking LLM internals."""

        if preparation.kind == "single_event":
            if preparation.event is not None:
                yield preparation.event
            return

        direct_execution = preparation.direct_execution
        if not _is_general_chat_execution(direct_execution):
            yield _error_event(
                "UNSUPPORTED_UNCONFIRMED_CAPABILITY",
                "该请求暂时无法通过当前对话通道处理。",
                retryable=False,
            )
            return

        message = direct_execution.inputs["message"]
        assert isinstance(message, str)
        # Delay Dialogue imports until the package graph has finished loading:
        # Dialogue Agent services depend on Interaction dispatch contracts.
        from app.platform.dialogue.application import (
            StreamingConversationCommand,
            StreamingConversationPersistenceError,
        )

        stream: AsyncIterator[StreamingConversationEvent] | None = None
        try:
            if preparation.principal is None:
                raise ValueError("请求主体无效。")
            stream = await self._streaming_conversation.execute(
                StreamingConversationCommand(
                    principal=preparation.principal,
                    message=message,
                    conversation_id=preparation.conversation_id,
                )
            )
            conversation_id, first_event = await asyncio.wait_for(
                _prime_stream(stream),
                timeout=settings.llm_stream_first_activity_timeout_seconds,
            )
            assert first_event.chunk is not None
            first_chunk = first_event.chunk
        except asyncio.TimeoutError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("UPSTREAM_TIMEOUT", "上游模型响应超时。")
            return
        except ValueError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("CHAT_INPUT_INVALID", "请求内容无效。", retryable=False)
            return
        except ConversationAccessDeniedError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("CONVERSATION_ACCESS_DENIED", "会话不可用。")
            return
        except StreamingConversationPersistenceError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("CONVERSATION_PERSISTENCE_ERROR", "对话暂时无法保存。")
            return
        except Exception:  # noqa: BLE001 - never expose provider internals
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("UPSTREAM_UNAVAILABLE", "上游模型暂时不可用。")
            return

        request_id = str(uuid4())
        model = first_chunk.model or "unknown"
        prompt_version = first_chunk.prompt_version or "llm-chat-v1"
        latest = first_chunk
        try:
            yield InteractionStreamEvent(
                "meta",
                {
                    "request_id": request_id,
                    "conversation_id": str(conversation_id),
                    "model": model,
                    "prompt_version": prompt_version,
                },
            )
            completed_result = None
            async for event in _stream_with_heartbeats(
                stream,
                first_event,
                is_disconnected=is_disconnected,
            ):
                if await is_disconnected():
                    return
                if event is None:
                    yield InteractionStreamEvent("heartbeat", {"request_id": request_id})
                    continue
                if event.kind == "completed":
                    completed_result = event.result
                    continue
                if event.kind != "delta" or event.chunk is None:
                    continue
                latest = event.chunk
                if event.chunk.content:
                    yield InteractionStreamEvent(
                        "delta",
                        {"request_id": request_id, "content": event.chunk.content},
                    )
            if await is_disconnected():
                return
            if completed_result is None:
                raise RuntimeError("流式 Conversation 未正常完成。")
            yield InteractionStreamEvent(
                "complete",
                {
                    "request_id": request_id,
                    "model": completed_result.model or latest.model or model,
                    "prompt_version": (
                        completed_result.prompt_version
                        or latest.prompt_version
                        or prompt_version
                    ),
                    "usage": {
                        "input_tokens": completed_result.input_tokens,
                        "output_tokens": completed_result.output_tokens,
                        "total_tokens": completed_result.total_tokens,
                    },
                },
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            yield _error_event("UPSTREAM_TIMEOUT", "上游模型响应超时。")
        except StreamingConversationPersistenceError:
            yield _error_event("CONVERSATION_PERSISTENCE_ERROR", "对话暂时无法保存。")
        except Exception:  # noqa: BLE001 - never expose provider internals
            yield _error_event("UPSTREAM_STREAM_ERROR", "模型生成过程中发生错误。")
        finally:
            await _close_stream(stream)


def _is_general_chat_execution(
    execution: DirectCapabilityExecution | None,
) -> bool:
    if execution is None:
        return False
    return (
        execution.capability_code == "chat.general"
        and execution.dispatch_key == "llm.chat"
        and isinstance(execution.inputs.get("message"), str)
        and bool(execution.inputs["message"].strip())
    )


def _single_error(code: str, message: str) -> InteractionStreamPreparation:
    return InteractionStreamPreparation(
        kind="single_event",
        event=_error_event(code, message, retryable=False),
    )


def _conversation_access_denied_result() -> GatewayResult:
    return GatewayResult(
        status="rejected",
        message="会话不可用。",
        error_code="CONVERSATION_ACCESS_DENIED",
    )


def _gateway_result_from_agent_turn(result: DialogueAgentTurnResult) -> GatewayResult:
    """保持确认 HTTP 响应外形，Dialogue 只返回与协议无关的受控终态。"""

    return GatewayResult(
        status=result.status,
        message=result.message,
        execution_result=result.execution_result,
        error_code=result.error_code,
        conversation_id=result.conversation_id,
    )


def _result_event(result: GatewayResult) -> InteractionStreamEvent:
    if result.status == "pending" and result.proposal is not None:
        data: dict[str, object] = {
            "proposal_id": result.proposal.proposal_id,
            "state": result.proposal.state,
            "summary": result.proposal.summary,
            "confirmation_prompt": result.proposal.confirmation_prompt,
        }
        if result.conversation_id is not None:
            data["conversation_id"] = str(result.conversation_id)
        return InteractionStreamEvent(
            "approval_required",
            data,
        )
    return InteractionStreamEvent(
        "result",
        {
            "status": result.status,
            "message": result.message,
            "error_code": result.error_code,
        },
    )


def _is_pending_agent(result: GatewayResult) -> bool:
    return (
        result.status == "pending"
        and result.proposal is not None
        and result.proposal.capability_type == "agent"
    )


def _error_event(
    code: str,
    message: str,
    *,
    retryable: bool = True,
) -> InteractionStreamEvent:
    return InteractionStreamEvent(
        "error",
        {"code": code, "message": message, "retryable": retryable},
    )


async def _prime_stream(
    stream: AsyncIterator[StreamingConversationEvent],
) -> tuple[UUID, StreamingConversationEvent]:
    conversation_id: UUID | None = None
    try:
        async for event in stream:
            if event.kind == "started":
                conversation_id = event.conversation_id
                continue
            if (
                event.kind == "delta"
                and event.chunk is not None
                and (event.chunk.has_upstream_activity or event.chunk.content.strip())
            ):
                if conversation_id is None:
                    raise RuntimeError("流式 Conversation 缺少会话标识。")
                return conversation_id, event
    except Exception:
        await _close_stream(stream)
        raise

    await _close_stream(stream)
    raise RuntimeError("LLM returned an empty response.")


async def _stream_with_heartbeats(
    stream: AsyncIterator[StreamingConversationEvent],
    first_event: StreamingConversationEvent,
    *,
    is_disconnected: DisconnectChecker,
) -> AsyncIterator[StreamingConversationEvent | None]:
    yield first_event
    deadline = monotonic() + settings.llm_stream_total_timeout_seconds
    last_chunk_at = monotonic()
    next_event = asyncio.create_task(anext(stream))
    try:
        while True:
            now = monotonic()
            remaining = min(
                deadline - now,
                settings.llm_stream_idle_timeout_seconds - (now - last_chunk_at),
                settings.llm_stream_heartbeat_seconds,
            )
            if remaining <= 0:
                raise asyncio.TimeoutError
            done, _ = await asyncio.wait({next_event}, timeout=remaining)
            if not done:
                if await is_disconnected():
                    return
                yield None
                continue
            try:
                event = next_event.result()
            except StopAsyncIteration:
                return
            last_chunk_at = monotonic()
            yield event
            if event.kind == "completed":
                return
            next_event = asyncio.create_task(anext(stream))
    finally:
        if not next_event.done():
            next_event.cancel()
            await asyncio.gather(next_event, return_exceptions=True)


async def _close_stream(stream: AsyncIterator[object] | None) -> None:
    if stream is None:
        return
    close = getattr(stream, "aclose", None)
    if close is not None:
        await close()
