from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.platform.workflow.domain import WorkflowRun


@dataclass(frozen=True, slots=True)
class WorkflowCommandReceipt:
    run_id: UUID
    command_type: str
    command_id: str


class WorkflowRepositoryPort(Protocol):
    """Workflow 聚合及其安全事件的原子读写端口。"""

    def get(self, run_id: UUID) -> WorkflowRun | None: ...

    def get_for_update(self, run_id: UUID) -> WorkflowRun | None: ...

    def get_owned(self, *, run_id: UUID, owner_subject: str) -> WorkflowRun | None: ...

    def create_or_get(self, run: WorkflowRun) -> WorkflowRun: ...

    def save(
        self,
        run: WorkflowRun,
        *,
        command_receipt: WorkflowCommandReceipt | None = None,
    ) -> None: ...

    def has_processed_command(
        self,
        *,
        run_id: UUID,
        command_type: str,
        command_id: str,
    ) -> bool: ...
