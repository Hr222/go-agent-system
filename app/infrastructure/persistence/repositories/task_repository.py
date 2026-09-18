from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models.task import (
    TaskAttemptRecord,
    TaskCommandReceiptRecord,
    TaskEventRecord,
    TaskRecord,
)
from app.infrastructure.persistence.task_mapper import (
    attempt_to_record,
    event_to_record,
    task_from_records,
    task_to_record,
    update_attempt_record,
    update_task_record,
)
from app.platform.task.domain import Task
from app.platform.task.errors import TaskNotFoundError, TaskSchemaUnavailableError
from app.platform.task.ports import TaskCommandReceipt, TaskRepositoryPort

TASK_SCHEMA_SETUP_GUIDE = "任务数据表尚未初始化。请先执行 sql/013_task_lifecycle.sql。"


def _is_missing_task_schema(exc: SQLAlchemyError) -> bool:
    message = str(exc).lower()
    return ("undefinedtable" in message or "does not exist" in message) and "task" in message


class PostgresTaskRepository(TaskRepositoryPort):
    """Task 聚合的 PostgreSQL 适配器；事务提交由本适配器统一管理。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: UUID) -> Task | None:
        try:
            return self._load(task_id)
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def get_for_update(self, task_id: UUID) -> Task | None:
        try:
            return self._load(task_id, lock=True)
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def get_next_queued_for_update(self, *, now: datetime) -> Task | None:
        """锁定一个到期排队任务，锁保持到后续聚合保存提交。"""

        try:
            statement = (
                select(TaskRecord)
                .where(
                    TaskRecord.status == "queued",
                    TaskRecord.available_at <= now,
                )
                .order_by(
                    TaskRecord.available_at.asc(),
                    TaskRecord.created_at.asc(),
                    TaskRecord.id.asc(),
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            record = self.session.scalar(statement)
            if record is None:
                self.session.rollback()
                return None
            return self._from_task_record(record)
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def release_claim_slot(self) -> None:
        """释放尚未写入领取事实的候选锁。"""

        self.session.rollback()

    def create_or_get_submission(self, task: Task) -> Task:
        try:
            record = task_to_record(task)
            self.session.add(record)
            self.session.flush()
            self.session.add(event_to_record(task.events[0]))
            self.session.commit()
            return task
        except IntegrityError:
            self.session.rollback()
            try:
                existing = self._find_submission(
                    owner_subject=task.owner_subject,
                    task_type=task.task_type,
                    idempotency_key=task.idempotency_key,
                )
            except SQLAlchemyError as exc:
                self._translate_schema_error(exc)
                raise
            if existing is None:
                raise
            return existing
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def save(
        self,
        task: Task,
        *,
        command_receipt: TaskCommandReceipt | None = None,
    ) -> None:
        try:
            record = self.session.scalar(
                select(TaskRecord).where(TaskRecord.id == task.id).with_for_update()
            )
            if record is None:
                raise TaskNotFoundError("任务不存在。")
            update_task_record(record, task)

            attempt_records = {
                item.id: item
                for item in self.session.scalars(
                    select(TaskAttemptRecord).where(TaskAttemptRecord.task_id == task.id)
                ).all()
            }
            for attempt in task.attempts:
                existing = attempt_records.get(attempt.id)
                if existing is None:
                    self.session.add(attempt_to_record(attempt))
                else:
                    update_attempt_record(existing, attempt)

            event_ids = {
                item.id
                for item in self.session.scalars(
                    select(TaskEventRecord).where(TaskEventRecord.task_id == task.id)
                ).all()
            }
            for event in task.events:
                if event.id not in event_ids:
                    self.session.add(event_to_record(event))

            if command_receipt is not None:
                receipt = self.session.scalar(
                    select(TaskCommandReceiptRecord).where(
                        TaskCommandReceiptRecord.task_id == command_receipt.task_id,
                        TaskCommandReceiptRecord.command_type == command_receipt.command_type,
                        TaskCommandReceiptRecord.command_id == command_receipt.command_id,
                    )
                )
                if receipt is None:
                    self.session.add(
                        TaskCommandReceiptRecord(
                            id=uuid4(),
                            task_id=command_receipt.task_id,
                            command_type=command_receipt.command_type,
                            command_id=command_receipt.command_id,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def has_processed_command(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> bool:
        try:
            return (
                self.session.scalar(
                    select(TaskCommandReceiptRecord.id).where(
                        TaskCommandReceiptRecord.task_id == task_id,
                        TaskCommandReceiptRecord.command_type == command_type,
                        TaskCommandReceiptRecord.command_id == command_id,
                    )
                )
                is not None
            )
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def mark_command_processed(
        self,
        *,
        task_id: UUID,
        command_type: str,
        command_id: str,
    ) -> None:
        """兼容 Port 的低层方法；新 Application 始终通过 save 原子写入回执。"""

        try:
            receipt = self.session.scalar(
                select(TaskCommandReceiptRecord.id).where(
                    TaskCommandReceiptRecord.task_id == task_id,
                    TaskCommandReceiptRecord.command_type == command_type,
                    TaskCommandReceiptRecord.command_id == command_id,
                )
            )
            if receipt is not None:
                return
            self.session.add(
                TaskCommandReceiptRecord(
                    id=uuid4(), task_id=task_id, command_type=command_type,
                    command_id=command_id, created_at=datetime.now(timezone.utc),
                )
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def _find_submission(
        self,
        *,
        owner_subject: str,
        task_type: str,
        idempotency_key: str,
    ) -> Task | None:
        record = self.session.scalar(
            select(TaskRecord).where(
                TaskRecord.owner_subject == owner_subject,
                TaskRecord.task_type == task_type,
                TaskRecord.idempotency_key == idempotency_key,
            )
        )
        if record is None:
            return None
        return self._from_task_record(record)

    def _load(self, task_id: UUID, *, lock: bool = False) -> Task | None:
        statement = select(TaskRecord).where(TaskRecord.id == task_id)
        if lock:
            statement = statement.with_for_update()
        record = self.session.scalar(statement)
        if record is None:
            return None
        return self._from_task_record(record)

    def _from_task_record(self, record: TaskRecord) -> Task:
        attempts = self.session.scalars(
            select(TaskAttemptRecord)
            .where(TaskAttemptRecord.task_id == record.id)
            .order_by(TaskAttemptRecord.number.asc())
        ).all()
        events = self.session.scalars(
            select(TaskEventRecord)
            .where(TaskEventRecord.task_id == record.id)
            .order_by(TaskEventRecord.sequence.asc())
        ).all()
        return task_from_records(record, list(attempts), list(events))

    @staticmethod
    def _translate_schema_error(exc: SQLAlchemyError) -> None:
        if _is_missing_task_schema(exc):
            raise TaskSchemaUnavailableError(TASK_SCHEMA_SETUP_GUIDE) from exc


__all__ = ["PostgresTaskRepository", "TASK_SCHEMA_SETUP_GUIDE"]
