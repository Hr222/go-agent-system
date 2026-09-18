from __future__ import annotations

from datetime import datetime
from threading import RLock
from uuid import UUID

from app.platform.task.domain import Task
from app.platform.task.ports import TaskCommandReceipt


class InMemoryTaskRepository:
    """TM-01 的确定性测试替身；不提供并发或持久化保证。"""

    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}
        self._submissions: dict[tuple[str, str, str], UUID] = {}
        self._command_receipts: set[tuple[UUID, str, str]] = set()
        self._claim_lock = RLock()
        self._claim_slot_held = False

    def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    def get_for_update(self, task_id: UUID) -> Task | None:
        return self.get(task_id)

    def get_next_queued_for_update(self, *, now: datetime) -> Task | None:
        self._claim_lock.acquire()
        for task in sorted(
            self._tasks.values(),
            key=lambda item: (item.available_at, item.created_at, item.id),
        ):
            if task.status.value == "queued" and task.available_at <= now:
                self._claim_slot_held = True
                return task
        self._claim_lock.release()
        return None

    def create_or_get_submission(self, task: Task) -> Task:
        existing = self.find_by_submission(
            owner_subject=task.owner_subject,
            task_type=task.task_type,
            idempotency_key=task.idempotency_key,
        )
        if existing is not None:
            return existing
        self.save(task)
        return task

    def save(
        self,
        task: Task,
        *,
        command_receipt: TaskCommandReceipt | None = None,
    ) -> None:
        try:
            self._tasks[task.id] = task
            self._submissions[(task.owner_subject, task.task_type, task.idempotency_key)] = task.id
            if command_receipt is not None:
                self.mark_command_processed(
                    task_id=command_receipt.task_id,
                    command_type=command_receipt.command_type,
                    command_id=command_receipt.command_id,
                )
        finally:
            if self._claim_slot_held:
                self._claim_slot_held = False
                self._claim_lock.release()

    def release_claim_slot(self) -> None:
        if self._claim_slot_held:
            self._claim_slot_held = False
            self._claim_lock.release()

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
