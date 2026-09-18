from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from app.platform.task.domain import Task, TaskStatus


@dataclass(frozen=True, slots=True)
class SubmitTaskCommand:
    owner_subject: str
    task_type: str
    idempotency_key: str
    input_fingerprint: str
    max_attempts: int
    display_metadata: Mapping[str, str] | None = None
    allow_manual_retry: bool = True


@dataclass(frozen=True, slots=True)
class CancelTaskCommand:
    task_id: UUID
    command_id: str


@dataclass(frozen=True, slots=True)
class RequeueTaskCommand:
    task_id: UUID
    command_id: str


@dataclass(frozen=True, slots=True)
class RetryTaskCommand:
    task_id: UUID
    command_id: str


@dataclass(frozen=True, slots=True)
class RecoverTaskCommand:
    task_id: UUID
    command_id: str
    retry_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TaskView:
    id: UUID
    task_type: str
    owner_subject: str
    status: TaskStatus
    attempt_count: int
    max_attempts: int
    available_at: datetime
    result_summary: str | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task) -> TaskView:
        return cls(
            id=task.id,
            task_type=task.task_type,
            owner_subject=task.owner_subject,
            status=task.status,
            attempt_count=task.attempt_count,
            max_attempts=task.max_attempts,
            available_at=task.available_at,
            result_summary=task.result_summary,
            failure_code=task.failure_code,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
