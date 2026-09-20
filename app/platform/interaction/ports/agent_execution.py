"""已授权 Agent 调用的可替换执行策略契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.security.domain.principal import RequestPrincipal

AgentExecutionStatus = Literal["completed", "accepted", "failed"]


@dataclass(frozen=True, slots=True)
class AgentExecutionCommand:
    """只向已获授权的执行策略传递可信调用上下文。"""

    call: StructuredAgentCall
    capability: PlatformCapability
    principal: RequestPrincipal

    def __post_init__(self) -> None:
        if self.capability.capability_type != "agent":
            raise ValueError("执行策略只能接收 Agent 能力。")
        if self.capability.code != self.call.capability_code:
            raise ValueError("执行策略的能力目录与调用目标不一致。")


@dataclass(frozen=True, slots=True)
class AgentExecutionOutcome:
    """策略内部结果；延迟引用不绑定 Task 或其他执行引擎。"""

    status: AgentExecutionStatus
    output: object | None = None
    execution_reference: str | None = None
    error_code: str | None = None
    message: str | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        if self.status == "completed":
            if self.execution_reference is not None:
                raise ValueError("已完成结果不能携带延迟执行引用。")
            if self.error_code is not None or self.message is not None:
                raise ValueError("已完成结果不能携带失败信息。")
            return
        if self.status == "accepted":
            if self.output is not None:
                raise ValueError("已接收结果不能携带同步输出。")
            if not _has_text(self.execution_reference):
                raise ValueError("已接收结果必须携带执行引用。")
            if self.error_code is not None or self.message is not None:
                raise ValueError("已接收结果不能携带失败信息。")
            return
        if self.status == "failed":
            if self.output is not None or self.execution_reference is not None:
                raise ValueError("失败结果不能携带输出或执行引用。")
            if not _has_text(self.error_code) or not _has_text(self.message):
                raise ValueError("失败结果必须携带受控错误码和消息。")
            return
        raise ValueError("执行策略结果状态无效。")

    @classmethod
    def completed(cls, output: object) -> "AgentExecutionOutcome":
        return cls(status="completed", output=output)

    @classmethod
    def accepted(cls, execution_reference: str) -> "AgentExecutionOutcome":
        return cls(status="accepted", execution_reference=execution_reference.strip())

    @classmethod
    def failed(
        cls,
        *,
        error_code: str,
        message: str,
        retryable: bool = False,
    ) -> "AgentExecutionOutcome":
        return cls(
            status="failed",
            error_code=error_code.strip(),
            message=message.strip(),
            retryable=retryable,
        )


class AgentExecutionStrategyPort(Protocol):
    """执行可信 Agent 调用的最小替换边界。"""

    def execute(self, command: AgentExecutionCommand) -> AgentExecutionOutcome: ...


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "AgentExecutionCommand",
    "AgentExecutionOutcome",
    "AgentExecutionStatus",
    "AgentExecutionStrategyPort",
]
