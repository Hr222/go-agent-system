from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.platform.task.domain import Task


class TaskRepositoryPort(Protocol):
    """Task Application 依赖的最小读写与命令回执边界。"""

    def get(self, task_id: UUID) -> Task | None: ...

    def save(self, task: Task) -> None: ...

    def find_by_submission(
        self,
        *,
        owner_subject: str,
        task_type: str,
        idempotency_key: str,
    ) -> Task | None: ...

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
