from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.platform.task.domain import Task


@dataclass(frozen=True, slots=True)
class TaskCommandReceipt:
    """与聚合状态同事务写入的幂等命令回执。"""

    task_id: UUID
    command_type: str
    command_id: str


class TaskRepositoryPort(Protocol):
    """Task Application 依赖的原子聚合读写与命令回执边界。"""

    def get(self, task_id: UUID) -> Task | None: ...

    def get_for_update(self, task_id: UUID) -> Task | None: ...

    def create_or_get_submission(self, task: Task) -> Task: ...

    def save(
        self,
        task: Task,
        *,
        command_receipt: TaskCommandReceipt | None = None,
    ) -> None: ...

    def has_processed_command(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> bool: ...

    def mark_command_processed(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> None: ...
