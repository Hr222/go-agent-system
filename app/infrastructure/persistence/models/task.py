from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class TaskRecord(Base):
    """Task 聚合根的 PostgreSQL 记录；外部协议不可直接使用。"""

    __tablename__ = "task"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject", "task_type", "idempotency_key", name="uq_task_submission"
        ),
        CheckConstraint("btrim(task_type) <> ''", name="chk_task_type_not_blank"),
        CheckConstraint("btrim(owner_subject) <> ''", name="chk_task_owner_not_blank"),
        CheckConstraint("btrim(idempotency_key) <> ''", name="chk_task_idempotency_not_blank"),
        CheckConstraint(
            "btrim(input_fingerprint) <> ''", name="chk_task_input_fingerprint_not_blank"
        ),
        CheckConstraint("max_attempts > 0", name="chk_task_max_attempts_positive"),
        CheckConstraint(
            "status IN ('queued', 'running', 'retry_wait', 'cancel_requested', "
            "'succeeded', 'failed', 'cancelled')",
            name="chk_task_status",
        ),
        CheckConstraint(
            "jsonb_typeof(display_metadata) = 'object'",
            name="chk_task_display_metadata_object",
        ),
        Index("idx_task_status_available_at", "status", "available_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_subject: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    max_attempts: Mapped[int] = mapped_column(BIGINT, nullable=False)
    available_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    display_metadata: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    allow_manual_retry: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)
    result_fingerprint: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)


class TaskAttemptRecord(Base):
    """Task 内部执行尝试；lease token 不会映射到安全投影或事件。"""

    __tablename__ = "task_attempt"
    __table_args__ = (
        UniqueConstraint("task_id", "number", name="uq_task_attempt_number"),
        UniqueConstraint("task_id", "worker_id", "claim_id", name="uq_task_attempt_claim"),
        CheckConstraint("number > 0", name="chk_task_attempt_number_positive"),
        CheckConstraint("btrim(worker_id) <> ''", name="chk_task_attempt_worker_not_blank"),
        CheckConstraint("btrim(claim_id) <> ''", name="chk_task_attempt_claim_not_blank"),
        CheckConstraint("btrim(lease_token) <> ''", name="chk_task_attempt_lease_not_blank"),
        CheckConstraint(
            "lease_expires_at > created_at", name="chk_task_attempt_lease_after_create"
        ),
        CheckConstraint(
            "status IN ('active', 'succeeded', 'failed', 'cancelled', 'expired')",
            name="chk_task_attempt_status",
        ),
        CheckConstraint(
            "renewal_sequence >= 0", name="chk_task_attempt_renewal_sequence_nonnegative"
        ),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN "
            "('transient', 'permanent', 'lease_expired')",
            name="chk_task_attempt_failure_category",
        ),
        Index(
            "uq_task_attempt_one_active",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(BIGINT, nullable=False)
    worker_id: Mapped[str] = mapped_column(Text, nullable=False)
    claim_id: Mapped[str] = mapped_column(Text, nullable=False)
    lease_token: Mapped[str] = mapped_column(Text, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    renewal_sequence: Mapped[int] = mapped_column(BIGINT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    failure_category: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    result_fingerprint: Mapped[str | None] = mapped_column(Text)


class TaskEventRecord(Base):
    __tablename__ = "task_event"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_event_sequence"),
        UniqueConstraint("task_id", "transition_id", name="uq_task_event_transition"),
        CheckConstraint("sequence > 0", name="chk_task_event_sequence_positive"),
        CheckConstraint("btrim(transition_id) <> ''", name="chk_task_event_transition_not_blank"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="chk_task_event_metadata_object"),
        CheckConstraint(
            "event_type IN ('TASK_CREATED', 'TASK_CLAIMED', 'TASK_CANCEL_REQUESTED', "
            "'TASK_CANCELLED', 'TASK_SUCCEEDED', 'TASK_FAILED', 'TASK_RETRY_SCHEDULED', "
            "'TASK_REQUEUED', 'TASK_RETRY_REQUESTED', 'TASK_RECOVERED')",
            name="chk_task_event_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(BIGINT, nullable=False)
    transition_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict[str, str | int]] = mapped_column(
        "metadata", JSONB, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class TaskCommandReceiptRecord(Base):
    __tablename__ = "task_command_receipt"
    __table_args__ = (
        UniqueConstraint("task_id", "command_type", "command_id", name="uq_task_command_receipt"),
        CheckConstraint("btrim(command_type) <> ''", name="chk_task_receipt_type_not_blank"),
        CheckConstraint("btrim(command_id) <> ''", name="chk_task_receipt_id_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    command_type: Mapped[str] = mapped_column(Text, nullable=False)
    command_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
