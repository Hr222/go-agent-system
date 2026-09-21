from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models.workflow import (
    WorkflowCommandReceiptRecord,
    WorkflowEventRecord,
    WorkflowNodeRunRecord,
    WorkflowRunRecord,
)
from app.infrastructure.persistence.workflow_mapper import (
    event_to_record,
    node_to_record,
    run_from_records,
    run_to_record,
    update_node_record,
    update_run_record,
)
from app.platform.workflow.domain import WorkflowRun
from app.platform.workflow.ports import WorkflowCommandReceipt, WorkflowRepositoryPort


class PostgresWorkflowRepository(WorkflowRepositoryPort):
    """Workflow Run 聚合的 PostgreSQL 适配器。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, run_id: UUID) -> WorkflowRun | None:
        return self._load(run_id)

    def get_for_update(self, run_id: UUID) -> WorkflowRun | None:
        return self._load(run_id, lock=True)

    def get_owned(self, *, run_id: UUID, owner_subject: str) -> WorkflowRun | None:
        record = self.session.scalar(
            select(WorkflowRunRecord).where(
                WorkflowRunRecord.id == run_id,
                WorkflowRunRecord.owner_subject == owner_subject,
            )
        )
        return self._from_record(record) if record is not None else None

    def create_or_get(self, run: WorkflowRun) -> WorkflowRun:
        try:
            self.session.add(run_to_record(run))
            self.session.flush()
            self.session.add_all([node_to_record(run.id, node) for node in run.nodes])
            self.session.add_all([event_to_record(event) for event in run.events])
            self.session.commit()
            return run
        except IntegrityError:
            self.session.rollback()
            record = self.session.scalar(
                select(WorkflowRunRecord).where(
                    WorkflowRunRecord.owner_subject == run.owner_subject,
                    WorkflowRunRecord.workflow_code == run.workflow_code,
                    WorkflowRunRecord.workflow_version == run.workflow_version,
                    WorkflowRunRecord.idempotency_key == run.idempotency_key,
                )
            )
            if record is None:
                raise
            return self._from_record(record)

    def save(
        self,
        run: WorkflowRun,
        *,
        command_receipt: WorkflowCommandReceipt | None = None,
    ) -> None:
        record = self.session.scalar(
            select(WorkflowRunRecord).where(WorkflowRunRecord.id == run.id).with_for_update()
        )
        if record is None:
            raise LookupError("Workflow 不存在。")
        update_run_record(record, run)
        existing_nodes = {
            item.id: item
            for item in self.session.scalars(
                select(WorkflowNodeRunRecord).where(WorkflowNodeRunRecord.run_id == run.id)
            ).all()
        }
        for node in run.nodes:
            existing = existing_nodes.get(node.id)
            if existing is None:
                self.session.add(node_to_record(run.id, node))
            else:
                update_node_record(existing, node)
        existing_events = {
            item.id
            for item in self.session.scalars(
                select(WorkflowEventRecord).where(WorkflowEventRecord.run_id == run.id)
            ).all()
        }
        for event in run.events:
            if event.id not in existing_events:
                self.session.add(event_to_record(event))
        if command_receipt is not None:
            exists = self.session.scalar(
                select(WorkflowCommandReceiptRecord.id).where(
                    WorkflowCommandReceiptRecord.run_id == command_receipt.run_id,
                    WorkflowCommandReceiptRecord.command_type == command_receipt.command_type,
                    WorkflowCommandReceiptRecord.command_id == command_receipt.command_id,
                )
            )
            if exists is None:
                self.session.add(
                    WorkflowCommandReceiptRecord(
                        id=uuid4(),
                        run_id=command_receipt.run_id,
                        command_type=command_receipt.command_type,
                        command_id=command_receipt.command_id,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        self.session.commit()

    def has_processed_command(self, *, run_id: UUID, command_type: str, command_id: str) -> bool:
        return (
            self.session.scalar(
                select(WorkflowCommandReceiptRecord.id).where(
                    WorkflowCommandReceiptRecord.run_id == run_id,
                    WorkflowCommandReceiptRecord.command_type == command_type,
                    WorkflowCommandReceiptRecord.command_id == command_id,
                )
            )
            is not None
        )

    def _load(self, run_id: UUID, *, lock: bool = False) -> WorkflowRun | None:
        statement = select(WorkflowRunRecord).where(WorkflowRunRecord.id == run_id)
        if lock:
            statement = statement.with_for_update()
        record = self.session.scalar(statement)
        return self._from_record(record) if record is not None else None

    def _from_record(self, record: WorkflowRunRecord) -> WorkflowRun:
        nodes = list(
            self.session.scalars(
                select(WorkflowNodeRunRecord)
                .where(WorkflowNodeRunRecord.run_id == record.id)
                .order_by(WorkflowNodeRunRecord.node_id.asc())
            ).all()
        )
        events = list(
            self.session.scalars(
                select(WorkflowEventRecord)
                .where(WorkflowEventRecord.run_id == record.id)
                .order_by(WorkflowEventRecord.sequence.asc())
            ).all()
        )
        return run_from_records(record, nodes, events)


__all__ = ["PostgresWorkflowRepository"]
