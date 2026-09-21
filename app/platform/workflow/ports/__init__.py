"""Workflow 的受控端口。"""

from app.platform.workflow.ports.executor import (
    WorkflowNodeExecutionCommand,
    WorkflowNodeExecutionOutcome,
    WorkflowNodeExecutorPort,
)
from app.platform.workflow.ports.registry import WorkflowDefinitionRegistryPort
from app.platform.workflow.ports.repository import (
    WorkflowCommandReceipt,
    WorkflowRepositoryPort,
)

__all__ = [
    "WorkflowCommandReceipt",
    "WorkflowDefinitionRegistryPort",
    "WorkflowNodeExecutionCommand",
    "WorkflowNodeExecutionOutcome",
    "WorkflowNodeExecutorPort",
    "WorkflowRepositoryPort",
]
