from __future__ import annotations

from datetime import datetime, timezone

from app.infrastructure.persistence.models.workflow import (
    WorkflowEventRecord,
    WorkflowNodeRunRecord,
    WorkflowRunRecord,
)
from app.infrastructure.persistence.workflow_mapper import run_from_records
from app.platform.workflow.domain import (
    WorkflowEventType,
    WorkflowNodeDefinition,
    WorkflowNodeStatus,
    WorkflowNodeType,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowVersion,
)


def test_workflow_run_mapper_restores_only_safe_facts() -> None:
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    version = WorkflowVersion(
        workflow_code="flow",
        version="v1",
        nodes=(WorkflowNodeDefinition("step", WorkflowNodeType.CAPABILITY, "capability.one"),),
    )
    run = WorkflowRun.create(
        version=version,
        owner_subject="user-1",
        idempotency_key="key-1",
        input_fingerprint="sha256:input",
        now=now,
    )
    run_record = WorkflowRunRecord(
        id=run.id,
        workflow_code=run.workflow_code,
        workflow_version=run.workflow_version,
        owner_subject=run.owner_subject,
        idempotency_key=run.idempotency_key,
        input_fingerprint=run.input_fingerprint,
        status=run.status.value,
        created_at=now,
        updated_at=now,
    )
    node = run.nodes[0]
    node_record = WorkflowNodeRunRecord(
        id=node.id,
        run_id=run.id,
        node_id=node.node_id,
        node_type=node.node_type.value,
        capability_code=node.capability_code,
        max_attempts=node.max_attempts,
        status=node.status.value,
        attempt_count=node.attempt_count,
        created_at=now,
        updated_at=now,
    )
    event = run.events[0]
    event_record = WorkflowEventRecord(
        id=event.id,
        run_id=run.id,
        sequence=event.sequence,
        transition_id=event.transition_id,
        event_type=event.event_type.value,
        event_metadata=dict(event.metadata),
        created_at=event.created_at,
    )

    restored = run_from_records(run_record, [node_record], [event_record])

    assert restored.id == run.id
    assert restored.status is WorkflowRunStatus.QUEUED
    assert restored.nodes[0].status is WorkflowNodeStatus.QUEUED
    assert restored.events[0].event_type is WorkflowEventType.RUN_CREATED
    assert not hasattr(node_record, "lease_token")
