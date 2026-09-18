from __future__ import annotations

from app.infrastructure.persistence.models.task import (
    TaskAttemptRecord,
    TaskEventRecord,
    TaskRecord,
)
from app.platform.task.domain import (
    AttemptStatus,
    FailureCategory,
    Task,
    TaskAttempt,
    TaskEvent,
    TaskEventType,
    TaskStatus,
)


def task_to_record(task: Task) -> TaskRecord:
    return TaskRecord(
        id=task.id,
        task_type=task.task_type,
        owner_subject=task.owner_subject,
        idempotency_key=task.idempotency_key,
        input_fingerprint=task.input_fingerprint,
        max_attempts=task.max_attempts,
        available_at=task.available_at,
        status=task.status.value,
        display_metadata=dict(task.display_metadata),
        allow_manual_retry=task.allow_manual_retry,
        created_at=task.created_at,
        updated_at=task.updated_at,
        cancel_requested_at=task.cancel_requested_at,
        result_summary=task.result_summary,
        result_fingerprint=task.result_fingerprint,
        failure_code=task.failure_code,
    )


def update_task_record(record: TaskRecord, task: Task) -> None:
    values = {
        "status": task.status.value,
        "available_at": task.available_at,
        "display_metadata": dict(task.display_metadata),
        "allow_manual_retry": task.allow_manual_retry,
        "updated_at": task.updated_at,
        "cancel_requested_at": task.cancel_requested_at,
        "result_summary": task.result_summary,
        "result_fingerprint": task.result_fingerprint,
        "failure_code": task.failure_code,
    }
    for name, value in values.items():
        setattr(record, name, value)


def attempt_to_record(attempt: TaskAttempt) -> TaskAttemptRecord:
    return TaskAttemptRecord(
        id=attempt.id,
        task_id=attempt.task_id,
        number=attempt.number,
        worker_id=attempt.worker_id,
        claim_id=attempt.claim_id,
        lease_token=attempt.lease_token,
        lease_expires_at=attempt.lease_expires_at,
        status=attempt.status.value,
        renewal_sequence=attempt.renewal_sequence,
        created_at=attempt.created_at,
        finished_at=attempt.finished_at,
        failure_category=(attempt.failure_category.value if attempt.failure_category else None),
        failure_code=attempt.failure_code,
        result_fingerprint=attempt.result_fingerprint,
    )


def update_attempt_record(record: TaskAttemptRecord, attempt: TaskAttempt) -> None:
    values = {
        "lease_expires_at": attempt.lease_expires_at,
        "status": attempt.status.value,
        "renewal_sequence": attempt.renewal_sequence,
        "finished_at": attempt.finished_at,
        "failure_category": (
            attempt.failure_category.value if attempt.failure_category else None
        ),
        "failure_code": attempt.failure_code,
        "result_fingerprint": attempt.result_fingerprint,
    }
    for name, value in values.items():
        setattr(record, name, value)


def event_to_record(event: TaskEvent) -> TaskEventRecord:
    return TaskEventRecord(
        id=event.id,
        task_id=event.task_id,
        sequence=event.sequence,
        transition_id=event.transition_id,
        event_type=event.event_type.value,
        event_metadata=dict(event.metadata),
        created_at=event.created_at,
    )


def task_from_records(
    record: TaskRecord,
    attempts: list[TaskAttemptRecord],
    events: list[TaskEventRecord],
) -> Task:
    return Task(
        id=record.id,
        task_type=record.task_type,
        owner_subject=record.owner_subject,
        idempotency_key=record.idempotency_key,
        input_fingerprint=record.input_fingerprint,
        max_attempts=record.max_attempts,
        available_at=record.available_at,
        status=TaskStatus(record.status),
        display_metadata=dict(record.display_metadata),
        allow_manual_retry=record.allow_manual_retry,
        created_at=record.created_at,
        updated_at=record.updated_at,
        cancel_requested_at=record.cancel_requested_at,
        result_summary=record.result_summary,
        result_fingerprint=record.result_fingerprint,
        failure_code=record.failure_code,
        attempts=[attempt_from_record(item) for item in attempts],
        events=[event_from_record(item) for item in events],
    )


def attempt_from_record(record: TaskAttemptRecord) -> TaskAttempt:
    return TaskAttempt(
        id=record.id,
        task_id=record.task_id,
        number=record.number,
        worker_id=record.worker_id,
        claim_id=record.claim_id,
        lease_token=record.lease_token,
        lease_expires_at=record.lease_expires_at,
        status=AttemptStatus(record.status),
        renewal_sequence=record.renewal_sequence,
        created_at=record.created_at,
        finished_at=record.finished_at,
        failure_category=(
            FailureCategory(record.failure_category) if record.failure_category else None
        ),
        failure_code=record.failure_code,
        result_fingerprint=record.result_fingerprint,
    )


def event_from_record(record: TaskEventRecord) -> TaskEvent:
    return TaskEvent(
        id=record.id,
        task_id=record.task_id,
        sequence=record.sequence,
        transition_id=record.transition_id,
        event_type=TaskEventType(record.event_type),
        metadata=dict(record.event_metadata),
        created_at=record.created_at,
    )
