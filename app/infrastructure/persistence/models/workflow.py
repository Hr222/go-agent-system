from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BIGINT, TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_run"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject",
            "workflow_code",
            "workflow_version",
            "idempotency_key",
            name="uq_workflow_run_submission",
        ),
        CheckConstraint("btrim(owner_subject) <> ''", name="chk_workflow_run_owner_not_blank"),
        CheckConstraint("btrim(workflow_code) <> ''", name="chk_workflow_run_code_not_blank"),
        CheckConstraint("btrim(workflow_version) <> ''", name="chk_workflow_run_version_not_blank"),
        CheckConstraint(
            "btrim(idempotency_key) <> ''", name="chk_workflow_run_idempotency_not_blank"
        ),
        CheckConstraint(
            "btrim(input_fingerprint) <> ''", name="chk_workflow_run_input_fingerprint_not_blank"
        ),
        CheckConstraint(
            "status IN ("
            "'queued', 'running', 'accepted', 'succeeded', 'failed', "
            "'cancel_requested', 'cancelled')",
            name="chk_workflow_run_status",
        ),
        Index("idx_workflow_run_owner_updated", "owner_subject", "updated_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    workflow_code: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    owner_subject: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class WorkflowNodeRunRecord(Base):
    __tablename__ = "workflow_node_run"
    __table_args__ = (
        UniqueConstraint("run_id", "node_id", name="uq_workflow_node_run_node"),
        CheckConstraint("btrim(node_id) <> ''", name="chk_workflow_node_run_node_not_blank"),
        CheckConstraint(
            "btrim(capability_code) <> ''", name="chk_workflow_node_run_capability_not_blank"
        ),
        CheckConstraint("max_attempts > 0", name="chk_workflow_node_run_max_attempts_positive"),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="chk_workflow_node_run_attempt_range",
        ),
        CheckConstraint(
            "status IN ("
            "'queued', 'running', 'accepted', 'succeeded', 'failed', "
            "'cancel_requested', 'cancelled', 'skipped')",
            name="chk_workflow_node_run_status",
        ),
        Index("idx_workflow_node_run_ready", "run_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workflow_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    max_attempts: Mapped[int] = mapped_column(BIGINT, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(BIGINT, nullable=False)
    execution_reference: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[str | None] = mapped_column(Text)
    output_fingerprint: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class WorkflowEventRecord(Base):
    __tablename__ = "workflow_event"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_workflow_event_sequence"),
        UniqueConstraint("run_id", "transition_id", name="uq_workflow_event_transition"),
        CheckConstraint("sequence > 0", name="chk_workflow_event_sequence_positive"),
        CheckConstraint(
            "btrim(transition_id) <> ''", name="chk_workflow_event_transition_not_blank"
        ),
        CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name="chk_workflow_event_metadata_object"
        ),
        Index("idx_workflow_event_run_sequence", "run_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workflow_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BIGINT, nullable=False)
    transition_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class WorkflowCommandReceiptRecord(Base):
    __tablename__ = "workflow_command_receipt"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "command_type", "command_id", name="uq_workflow_command_receipt"
        ),
        CheckConstraint("btrim(command_type) <> ''", name="chk_workflow_receipt_type_not_blank"),
        CheckConstraint("btrim(command_id) <> ''", name="chk_workflow_receipt_id_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workflow_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    command_type: Mapped[str] = mapped_column(Text, nullable=False)
    command_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
