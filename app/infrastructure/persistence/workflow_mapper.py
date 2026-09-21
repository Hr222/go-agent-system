from __future__ import annotations

from app.infrastructure.persistence.models.workflow import (
    WorkflowEventRecord,
    WorkflowNodeRunRecord,
    WorkflowRunRecord,
)
from app.platform.workflow.domain import (
    WorkflowEvent,
    WorkflowEventType,
    WorkflowNodeRun,
    WorkflowNodeStatus,
    WorkflowNodeType,
    WorkflowRun,
    WorkflowRunStatus,
)


def run_to_record(run: WorkflowRun) -> WorkflowRunRecord:
    return WorkflowRunRecord(
        id=run.id,
        workflow_code=run.workflow_code,
        workflow_version=run.workflow_version,
        owner_subject=run.owner_subject,
        idempotency_key=run.idempotency_key,
        input_fingerprint=run.input_fingerprint,
        status=run.status.value,
        result_summary=run.result_summary,
        failure_code=run.failure_code,
        cancel_requested_at=run.cancel_requested_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def update_run_record(record: WorkflowRunRecord, run: WorkflowRun) -> None:
    for name, value in {
        "status": run.status.value,
        "result_summary": run.result_summary,
        "failure_code": run.failure_code,
        "cancel_requested_at": run.cancel_requested_at,
        "updated_at": run.updated_at,
    }.items():
        setattr(record, name, value)


def node_to_record(run_id, node: WorkflowNodeRun) -> WorkflowNodeRunRecord:  # noqa: ANN001
    return WorkflowNodeRunRecord(
        id=node.id,
        run_id=run_id,
        node_id=node.node_id,
        node_type=node.node_type.value,
        capability_code=node.capability_code,
        max_attempts=node.max_attempts,
        status=node.status.value,
        attempt_count=node.attempt_count,
        execution_reference=node.execution_reference,
        result_summary=node.result_summary,
        output_fingerprint=node.output_fingerprint,
        failure_code=node.failure_code,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def update_node_record(record: WorkflowNodeRunRecord, node: WorkflowNodeRun) -> None:
    for name, value in {
        "status": node.status.value,
        "attempt_count": node.attempt_count,
        "execution_reference": node.execution_reference,
        "result_summary": node.result_summary,
        "output_fingerprint": node.output_fingerprint,
        "failure_code": node.failure_code,
        "updated_at": node.updated_at,
    }.items():
        setattr(record, name, value)


def event_to_record(event: WorkflowEvent) -> WorkflowEventRecord:
    return WorkflowEventRecord(
        id=event.id,
        run_id=event.run_id,
        sequence=event.sequence,
        transition_id=event.transition_id,
        event_type=event.event_type.value,
        event_metadata=dict(event.metadata),
        created_at=event.created_at,
    )


def run_from_records(
    record: WorkflowRunRecord,
    nodes: list[WorkflowNodeRunRecord],
    events: list[WorkflowEventRecord],
) -> WorkflowRun:
    return WorkflowRun(
        id=record.id,
        workflow_code=record.workflow_code,
        workflow_version=record.workflow_version,
        owner_subject=record.owner_subject,
        idempotency_key=record.idempotency_key,
        input_fingerprint=record.input_fingerprint,
        status=WorkflowRunStatus(record.status),
        result_summary=record.result_summary,
        failure_code=record.failure_code,
        cancel_requested_at=record.cancel_requested_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        nodes=[
            WorkflowNodeRun(
                id=node.id,
                node_id=node.node_id,
                node_type=WorkflowNodeType(node.node_type),
                capability_code=node.capability_code,
                max_attempts=node.max_attempts,
                status=WorkflowNodeStatus(node.status),
                attempt_count=node.attempt_count,
                execution_reference=node.execution_reference,
                result_summary=node.result_summary,
                output_fingerprint=node.output_fingerprint,
                failure_code=node.failure_code,
                created_at=node.created_at,
                updated_at=node.updated_at,
            )
            for node in nodes
        ],
        events=[
            WorkflowEvent(
                id=event.id,
                run_id=event.run_id,
                sequence=event.sequence,
                transition_id=event.transition_id,
                event_type=WorkflowEventType(event.event_type),
                metadata=dict(event.event_metadata),
                created_at=event.created_at,
            )
            for event in events
        ],
    )
