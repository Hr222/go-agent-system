from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from app.platform.conversation.errors import ConversationAccessDeniedError
from app.platform.dialogue.application.agent_continuation import (
    DialogueAgentContinuationCommand,
    DialogueAgentContinuationService,
)
from app.platform.dialogue.application.agent_invocation import (
    DialogueAgentInvocationCommand,
    DialogueAgentInvocationService,
)
from app.platform.dialogue.application.conversation_turn_coordinator import (
    ConversationTurnCoordinator,
    ConversationTurnLease,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.platform.security.domain.principal import RequestPrincipal
from app.shared.async_task import await_shielded_task

DialogueAgentTurnStatus = Literal["completed", "cancelled", "rejected", "failed"]


@dataclass(frozen=True, slots=True)
class DialogueAgentTurnCommand:
    """经 Interaction/Gateway 复核后才允许执行的 Agent 调用。"""

    conversation_id: UUID
    capability_code: str
    inputs: dict[str, object]
    principal: RequestPrincipal
    approved_dispatch: ApprovedCapabilityDispatch
    call: StructuredAgentCall


@dataclass(frozen=True, slots=True)
class DialogueAgentTurnResult:
    """Dialogue 轮次的受控终态，接口层负责映射为 Gateway 响应。"""

    status: DialogueAgentTurnStatus
    message: str
    conversation_id: UUID | None = None
    execution_result: object | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class DialogueAgentTurnPreparation:
    """锁内确认操作的输出：受控终态或可执行的已批准调用。"""

    result: DialogueAgentTurnResult | None = None
    command: DialogueAgentTurnCommand | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.command is None):
            raise ValueError("Agent 轮次准备结果必须且只能包含一个终态或执行命令。")


DialogueAgentTurnConfirmation = Callable[[], DialogueAgentTurnPreparation]


@dataclass(frozen=True, slots=True)
class DialogueAgentTurnRequest:
    """进入 Conversation 租约前不产生会话事实的确认轮次请求。"""

    conversation_id: UUID
    confirm: DialogueAgentTurnConfirmation


class DialogueAgentTurnWorkerPort(Protocol):
    """每轮私有同步 worker；适配器负责其 Session 与资源生命周期。"""

    def execute(self, command: DialogueAgentTurnCommand) -> DialogueAgentTurnResult:
        """执行已批准 Agent 调用和可选的 continuation。"""

    def close(self) -> None:
        """释放本轮私有资源。"""


class DialogueAgentTurnWorkerFactoryPort(Protocol):
    """在 worker 线程内创建不携带请求级持久化对象的执行器。"""

    def create(self) -> DialogueAgentTurnWorkerPort:
        """创建一轮 Agent 执行专用 worker。"""


class DialogueAgentTurnWorker(DialogueAgentTurnWorkerPort):
    """复用现有 Invocation 与 Continuation 服务完成一条同步事实链。"""

    def __init__(
        self,
        *,
        invocation: DialogueAgentInvocationService,
        continuation: DialogueAgentContinuationService | None,
    ) -> None:
        self._invocation = invocation
        self._continuation = continuation

    def execute(self, command: DialogueAgentTurnCommand) -> DialogueAgentTurnResult:
        try:
            invocation = self._invocation.invoke(
                DialogueAgentInvocationCommand(
                    conversation_id=command.conversation_id,
                    capability_code=command.capability_code,
                    inputs=dict(command.inputs),
                    principal=command.principal,
                    approved_dispatch=command.approved_dispatch,
                    call=command.call,
                    persist_call_event=False,
                )
            )
        except ConversationAccessDeniedError:
            return DialogueAgentTurnResult(
                status="rejected",
                message="会话不可用。",
                error_code="CONVERSATION_ACCESS_DENIED",
            )
        except Exception:  # noqa: BLE001 - Agent invocation keeps a controlled boundary
            return DialogueAgentTurnResult(
                status="failed",
                message="Agent 调用暂时无法完成。",
                conversation_id=command.conversation_id,
                error_code="DIALOGUE_AGENT_UNAVAILABLE",
            )

        if invocation.status != "completed":
            return DialogueAgentTurnResult(
                status=_terminal_status(invocation.status),
                message=invocation.message,
                conversation_id=invocation.conversation_id,
                execution_result=invocation.output,
                error_code=invocation.error_code,
            )

        if self._continuation is None:
            return DialogueAgentTurnResult(
                status="completed",
                message=invocation.message,
                conversation_id=invocation.conversation_id,
                execution_result=invocation.output,
            )

        continuation = self._continuation.execute(
            DialogueAgentContinuationCommand(
                conversation_id=invocation.conversation_id,
                call_id=invocation.call.call_id,
                principal=command.principal,
            )
        )
        if continuation.status == "completed":
            return DialogueAgentTurnResult(
                status="completed",
                message=continuation.message,
                conversation_id=continuation.conversation_id,
                execution_result={
                    "answer": continuation.answer,
                    "agent_result": invocation.output,
                    "model": continuation.model,
                    "prompt_version": continuation.prompt_version,
                    "usage": {
                        "input_tokens": continuation.input_tokens,
                        "output_tokens": continuation.output_tokens,
                        "total_tokens": continuation.total_tokens,
                    },
                },
            )
        return DialogueAgentTurnResult(
            status="failed",
            message=continuation.message,
            conversation_id=continuation.conversation_id,
            execution_result={"agent_result": invocation.output},
            error_code=continuation.error_code,
        )

    def close(self) -> None:
        """服务的资源由其私有 worker adapter 统一释放。"""


class DialogueAgentTurnExecutor:
    """在同一 Conversation 租约内监督已确认 Agent 的完整事实链。"""

    def __init__(
        self,
        *,
        coordinator: ConversationTurnCoordinator,
        worker_factory: DialogueAgentTurnWorkerFactoryPort,
    ) -> None:
        self._coordinator = coordinator
        self._worker_factory = worker_factory

    async def execute(self, request: DialogueAgentTurnRequest) -> DialogueAgentTurnResult:
        """等待租约后复核确认；启动后的 worker 由独立任务持有租约。"""

        self._validate_request(request)
        lease = await self._coordinator.acquire(request.conversation_id)
        confirmation_task = asyncio.create_task(asyncio.to_thread(request.confirm))
        try:
            preparation = await await_shielded_task(confirmation_task)
        except asyncio.CancelledError as cancellation_error:
            # If confirmation already consumed the one-shot state, finish the
            # approved turn in the background instead of abandoning a half-turn.
            try:
                preparation = confirmation_task.result()
            except BaseException:
                lease.release()
                raise cancellation_error
            if preparation.result is not None:
                lease.release()
                raise cancellation_error
            agent_command = preparation.command
            if agent_command is None:
                lease.release()
                raise cancellation_error
            try:
                supervisor = asyncio.create_task(
                    self._supervise_started_turn(lease, agent_command)
                )
            except BaseException:
                lease.release()
                raise cancellation_error
            supervisor.add_done_callback(_consume_background_exception)
            raise cancellation_error
        except BaseException:
            lease.release()
            raise

        if preparation.result is not None:
            lease.release()
            return preparation.result

        agent_command = preparation.command
        if agent_command is None:
            lease.release()
            raise RuntimeError("Agent 轮次未生成可执行命令。")

        try:
            supervisor = asyncio.create_task(
                self._supervise_started_turn(lease, agent_command)
            )
        except BaseException:
            lease.release()
            raise
        supervisor.add_done_callback(_consume_background_exception)

        # 客户端取消不能取消同步 worker；supervisor 会在事实链终态后释放租约。
        return await asyncio.shield(supervisor)

    async def _supervise_started_turn(
        self,
        lease: ConversationTurnLease,
        command: DialogueAgentTurnCommand,
    ) -> DialogueAgentTurnResult:
        try:
            return await asyncio.to_thread(self._execute_worker, command)
        except Exception:  # noqa: BLE001 - never leak worker internals across the boundary
            return DialogueAgentTurnResult(
                status="failed",
                message="Agent 调用暂时无法完成。",
                conversation_id=command.conversation_id,
                error_code="DIALOGUE_AGENT_UNAVAILABLE",
            )
        finally:
            lease.release()

    def _execute_worker(self, command: DialogueAgentTurnCommand) -> DialogueAgentTurnResult:
        worker = self._worker_factory.create()
        try:
            return worker.execute(command)
        finally:
            worker.close()

    @staticmethod
    def _validate_request(request: DialogueAgentTurnRequest) -> None:
        if not isinstance(request, DialogueAgentTurnRequest):
            raise ValueError("Agent 轮次请求无效。")
        if not isinstance(request.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if not callable(request.confirm):
            raise ValueError("Agent 确认操作无效。")


def _terminal_status(status: str) -> DialogueAgentTurnStatus:
    if status == "cancelled":
        return "cancelled"
    if status == "rejected":
        return "rejected"
    if status == "completed":
        return "completed"
    return "failed"


def _consume_background_exception(task: asyncio.Task[DialogueAgentTurnResult]) -> None:
    """已取消请求不再 await supervisor 时，主动回收其受控异常。"""

    if not task.cancelled():
        task.exception()


__all__ = [
    "DialogueAgentTurnCommand",
    "DialogueAgentTurnConfirmation",
    "DialogueAgentTurnExecutor",
    "DialogueAgentTurnPreparation",
    "DialogueAgentTurnRequest",
    "DialogueAgentTurnResult",
    "DialogueAgentTurnWorker",
    "DialogueAgentTurnWorkerFactoryPort",
    "DialogueAgentTurnWorkerPort",
]
