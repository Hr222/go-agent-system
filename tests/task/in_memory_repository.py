from __future__ import annotations

from datetime import datetime
from threading import RLock
from uuid import UUID

from app.platform.task.domain import Task
from app.platform.task.ports import (
    DueRetryCandidate,
    ExpiredTaskCandidate,
    TaskCommandReceipt,
    TaskEventPage,
    TaskListCursor,
    TaskListPage,
)


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

    def get_expired_attempts_for_update(
        self, *, now: datetime, limit: int
    ) -> list[ExpiredTaskCandidate]:
        candidates: list[ExpiredTaskCandidate] = []
        for task in sorted(self._tasks.values(), key=lambda item: (item.updated_at, item.id)):
            if task.status.value not in {"running", "cancel_requested"}:
                continue
            attempt = task.active_attempt
            if attempt is not None and attempt.lease_expires_at <= now:
                candidates.append(
                    ExpiredTaskCandidate(task.id, attempt.id, attempt.lease_expires_at)
                )
            if len(candidates) >= limit:
                break
        return candidates

    def get_due_retries_for_update(
        self, *, now: datetime, limit: int
    ) -> list[DueRetryCandidate]:
        candidates = [
            DueRetryCandidate(task.id, task.available_at)
            for task in sorted(
                self._tasks.values(), key=lambda item: (item.available_at, item.id)
            )
            if task.status.value == "retry_wait" and task.available_at <= now
        ]
        return candidates[:limit]

    def list_owned(
        self,
        *,
        owner_subject: str,
        limit: int,
        cursor: TaskListCursor | None,
    ) -> TaskListPage:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("任务列表大小必须是正整数。")
        tasks = [
            task
            for task in sorted(
                self._tasks.values(), key=lambda item: (item.updated_at, item.id), reverse=True
            )
            if task.owner_subject == owner_subject
        ]
        if cursor is not None:
            tasks = [
                task
                for task in tasks
                if task.updated_at < cursor.updated_at
                or (task.updated_at == cursor.updated_at and task.id < cursor.id)
            ]
        page = tasks[: limit + 1]
        has_more = len(page) > limit
        page_tasks = tuple(page[:limit])
        return TaskListPage(
            tasks=page_tasks,
            has_more=has_more,
            next_cursor=(
                TaskListCursor(updated_at=page_tasks[-1].updated_at, id=page_tasks[-1].id)
                if has_more
                else None
            ),
        )

    def get_owned(self, *, task_id: UUID, owner_subject: str) -> Task | None:
        task = self._tasks.get(task_id)
        return task if task is not None and task.owner_subject == owner_subject else None

    def read_owned_events(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        limit: int,
        after_sequence: int | None,
    ) -> TaskEventPage | None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("事件列表大小必须是正整数。")
        if after_sequence is not None and (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence <= 0
        ):
            raise ValueError("事件游标必须是正整数。")
        task = self.get_owned(task_id=task_id, owner_subject=owner_subject)
        if task is None:
            return None
        events = [
            event
            for event in task.events
            if after_sequence is None or event.sequence > after_sequence
        ]
        page = events[: limit + 1]
        has_more = len(page) > limit
        page_events = tuple(page[:limit])
        return TaskEventPage(
            events=page_events,
            has_more=has_more,
            next_after_sequence=page_events[-1].sequence if has_more else None,
        )

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
