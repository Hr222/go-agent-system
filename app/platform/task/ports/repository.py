from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.platform.task.domain import Task


@dataclass(frozen=True, slots=True)
class TaskCommandReceipt:
    """与聚合状态同事务写入的幂等命令回执。"""

    task_id: UUID
    command_type: str
    command_id: str


@dataclass(frozen=True, slots=True)
class ExpiredTaskCandidate:
    """恢复扫描锁定的最小候选，不携带 lease token 或任务输入。"""

    task_id: UUID
    attempt_id: UUID
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class DueRetryCandidate:
    """退避到期扫描锁定的任务候选。"""

    task_id: UUID
    available_at: datetime


class TaskRepositoryPort(Protocol):
    """Task Application 依赖的原子聚合读写与命令回执边界。"""

    def get(self, task_id: UUID) -> Task | None: ...

    def get_for_update(self, task_id: UUID) -> Task | None: ...

    def get_next_queued_for_update(self, *, now: datetime) -> Task | None: ...

    def get_expired_attempts_for_update(
        self, *, now: datetime, limit: int
    ) -> list[ExpiredTaskCandidate]: ...

    def get_due_retries_for_update(
        self, *, now: datetime, limit: int
    ) -> list[DueRetryCandidate]: ...

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
