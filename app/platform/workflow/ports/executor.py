from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol

from app.platform.security.domain import RequestPrincipal
from app.platform.workflow.domain import WorkflowNodeDefinition, WorkflowVersion

WorkflowNodeExecutionStatus = Literal["completed", "accepted", "failed"]


@dataclass(frozen=True, slots=True)
class WorkflowNodeExecutionCommand:
    """受控执行器接收的短生命周期上下文；输入不得写入事件或持久层。"""

    principal: RequestPrincipal
    version: WorkflowVersion
    node: WorkflowNodeDefinition
    inputs: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.principal, RequestPrincipal):
            raise ValueError("Workflow 执行主体无效。")
        if self.node.node_id not in {item.node_id for item in self.version.nodes}:
            raise ValueError("执行节点不属于当前 Workflow Version。")
        if not isinstance(self.inputs, Mapping):
            raise ValueError("节点输入必须是对象。")


@dataclass(frozen=True, slots=True)
class WorkflowNodeExecutionOutcome:
    status: WorkflowNodeExecutionStatus
    result_summary: str | None = None
    output_fingerprint: str | None = None
    execution_reference: str | None = None
    error_code: str | None = None
    message: str | None = None
    retryable: bool = False

    def __post_init__(self) -> None:
        if self.status == "completed":
            if (
                not self.result_summary
                or self.execution_reference
                or self.error_code
                or self.message
            ):
                raise ValueError("completed 结果必须只有安全结果摘要。")
            return
        if self.status == "accepted":
            if (
                not self.execution_reference
                or self.result_summary
                or self.error_code
                or self.message
            ):
                raise ValueError("accepted 结果必须只有不透明执行引用。")
            return
        if self.status == "failed":
            if (
                self.result_summary
                or self.execution_reference
                or not self.error_code
                or not self.message
            ):
                raise ValueError("failed 结果必须只有受控错误信息。")
            return
        raise ValueError("Workflow 节点执行结果状态无效。")

    @classmethod
    def completed(cls, result_summary: str, output_fingerprint: str | None = None):
        return cls(
            status="completed",
            result_summary=result_summary.strip(),
            output_fingerprint=output_fingerprint,
        )

    @classmethod
    def accepted(cls, execution_reference: str):
        return cls(status="accepted", execution_reference=execution_reference.strip())

    @classmethod
    def failed(cls, *, error_code: str, message: str, retryable: bool = False):
        return cls(
            status="failed",
            error_code=error_code.strip(),
            message=message.strip(),
            retryable=retryable,
        )


class WorkflowNodeExecutorPort(Protocol):
    def execute(self, command: WorkflowNodeExecutionCommand) -> WorkflowNodeExecutionOutcome: ...
