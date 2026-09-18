from __future__ import annotations

from uuid import UUID

from app.platform.task.domain import Task


class InMemoryTaskRepository:
    """TM-01 的确定性仓储替身；不提供并发或持久化保证。"""

    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}
        self._submissions: dict[tuple[str, str, str], UUID] = {}
        self._command_receipts: set[tuple[UUID, str, str]] = set()

    def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task
        self._submissions[(task.owner_subject, task.task_type, task.idempotency_key)] = task.id

    def find_by_submission(
        self,
        *,
        owner_subject: str,
        task_type: str,
        idempotency_key: str,
    ) -> Task | None:
        task_id = self._submissions.get((owner_subject, task_type, idempotency_key))
        return self._tasks.get(task_id) if task_id is not None else None

    def has_processed_command(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> bool:
        return (task_id, command_type, command_id) in self._command_receipts

    def mark_command_processed(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> None:
        self._command_receipts.add((task_id, command_type, command_id))
