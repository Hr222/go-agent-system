from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
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
    event_from_record,
    event_to_record,
    task_from_records,
    task_to_record,
    update_attempt_record,
    update_task_record,
)
from app.platform.task.domain import Task
from app.platform.task.errors import TaskNotFoundError, TaskSchemaUnavailableError
from app.platform.task.ports import (
    DueRetryCandidate,
    ExpiredTaskCandidate,
    TaskCommandReceipt,
    TaskEventPage,
    TaskListCursor,
    TaskListPage,
    TaskRepositoryPort,
)

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

    def get_expired_attempts_for_update(
        self, *, now: datetime, limit: int
    ) -> list[ExpiredTaskCandidate]:
        """锁定一批过期活动尝试；锁跳过保证多个恢复器不争用同一候选。"""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("候选批次大小必须是正整数。")
        try:
            rows = self.session.execute(
                select(
                    TaskRecord.id,
                    TaskAttemptRecord.id,
                    TaskAttemptRecord.lease_expires_at,
                )
                .join(TaskAttemptRecord, TaskAttemptRecord.task_id == TaskRecord.id)
                .where(
                    TaskRecord.status.in_(("running", "cancel_requested")),
                    TaskAttemptRecord.status == "active",
                    TaskAttemptRecord.lease_expires_at <= now,
                )
                .order_by(TaskAttemptRecord.lease_expires_at.asc(), TaskRecord.id.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            if not rows:
                self.session.rollback()
            return [
                ExpiredTaskCandidate(
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_expires_at=lease_expires_at,
                )
                for task_id, attempt_id, lease_expires_at in rows
            ]
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def get_due_retries_for_update(
        self, *, now: datetime, limit: int
    ) -> list[DueRetryCandidate]:
        """锁定到期 retry_wait 任务，避免多个重试调度器重复转换。"""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("候选批次大小必须是正整数。")
        try:
            rows = self.session.execute(
                select(TaskRecord.id, TaskRecord.available_at)
                .where(
                    TaskRecord.status == "retry_wait",
                    TaskRecord.available_at <= now,
                )
                .order_by(TaskRecord.available_at.asc(), TaskRecord.id.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            if not rows:
                self.session.rollback()
            return [
                DueRetryCandidate(task_id=task_id, available_at=available_at)
                for task_id, available_at in rows
            ]
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def list_owned(
        self,
        *,
        owner_subject: str,
        limit: int,
        cursor: TaskListCursor | None,
    ) -> TaskListPage:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("任务列表大小必须是正整数。")
        try:
            statement = select(TaskRecord).where(TaskRecord.owner_subject == owner_subject)
            if cursor is not None:
                statement = statement.where(
                    or_(
                        TaskRecord.updated_at < cursor.updated_at,
                        and_(
                            TaskRecord.updated_at == cursor.updated_at,
                            TaskRecord.id < cursor.id,
                        ),
                    )
                )
            records = list(
                self.session.scalars(
                    statement.order_by(
                        TaskRecord.updated_at.desc(), TaskRecord.id.desc()
                    ).limit(limit + 1)
                ).all()
            )
            has_more = len(records) > limit
            page_records = records[:limit]
            tasks = tuple(self._from_task_record(record) for record in page_records)
            return TaskListPage(
                tasks=tasks,
                has_more=has_more,
                next_cursor=(
                    TaskListCursor(
                        updated_at=tasks[-1].updated_at,
                        id=tasks[-1].id,
                    )
                    if has_more
                    else None
                ),
            )
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

    def get_owned(self, *, task_id: UUID, owner_subject: str) -> Task | None:
        try:
            record = self.session.scalar(
                select(TaskRecord).where(
                    TaskRecord.id == task_id,
                    TaskRecord.owner_subject == owner_subject,
                )
            )
            return self._from_task_record(record) if record is not None else None
        except SQLAlchemyError as exc:
            self.session.rollback()
            self._translate_schema_error(exc)
            raise

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
        try:
            task_exists = self.session.scalar(
                select(TaskRecord.id).where(
                    TaskRecord.id == task_id,
                    TaskRecord.owner_subject == owner_subject,
                )
            )
            if task_exists is None:
                return None
            statement = select(TaskEventRecord).where(TaskEventRecord.task_id == task_id)
            if after_sequence is not None:
                statement = statement.where(TaskEventRecord.sequence > after_sequence)
            records = list(
                self.session.scalars(
                    statement.order_by(TaskEventRecord.sequence.asc()).limit(limit + 1)
                ).all()
            )
            has_more = len(records) > limit
            page_records = records[:limit]
            events = tuple(event_from_record(record) for record in page_records)
            return TaskEventPage(
                events=events,
                has_more=has_more,
                next_after_sequence=events[-1].sequence if has_more else None,
            )
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
