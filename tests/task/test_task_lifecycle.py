from __future__ import annotations

import math
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.platform.task.application import (
    CancelTaskCommand,
    RecoverTaskCommand,
    RequeueTaskCommand,
    RetryTaskCommand,
    SubmitTaskCommand,
    TaskLifecycleService,
)
from app.platform.task.application.contracts import TaskView
from app.platform.task.application.executor_contracts import (
    ClaimTaskCommand,
    CompleteTaskCommand,
    ConfirmCancellationCommand,
    FailTaskCommand,
    RenewLeaseCommand,
)
from app.platform.task.domain import FailureCategory, TaskEvent, TaskEventType, TaskStatus
from app.platform.task.errors import (
    TaskIdempotencyConflictError,
    TaskLeaseRejectedError,
    TaskStateTransitionError,
)
from tests.task.in_memory_repository import InMemoryTaskRepository


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: int) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def harness() -> tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock]:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    return TaskLifecycleService(repository, clock=clock), repository, clock


def _submit(service: TaskLifecycleService, *, max_attempts: int = 3) -> TaskView:
    return service.submit(
        SubmitTaskCommand(
            owner_subject="user-1",
            task_type="tender.generate",
            idempotency_key="submit-1",
            input_fingerprint="input-sha-1",
            max_attempts=max_attempts,
            display_metadata={"title": "合成任务"},
        )
    )


def _claim(
    service: TaskLifecycleService,
    task_id: object,
    clock: MutableClock,
    *,
    claim_id: str = "claim-1",
    lease_token: str = "lease-1",
):
    return service.claim(
        ClaimTaskCommand(
            task_id=task_id,  # type: ignore[arg-type]
            worker_id="worker-1",
            claim_id=claim_id,
            lease_token=lease_token,
            lease_expires_at=clock.now + timedelta(minutes=5),
        )
    )


def test_submit_creates_initial_task_event_and_safe_view(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, _ = harness

    submitted = _submit(service)
    task = repository.get(submitted.id)

    assert submitted.status is TaskStatus.QUEUED
    assert submitted.attempt_count == 0
    assert task is not None
    assert task.events[0].event_type is TaskEventType.TASK_CREATED
    assert task.events[0].sequence == 1
    assert "input_fingerprint" not in {field.name for field in fields(TaskView)}
    assert "lease_token" not in {field.name for field in fields(TaskView)}


@pytest.mark.parametrize(
    "command",
    [
        SubmitTaskCommand("", "tender.generate", "key", "input", 1),
        SubmitTaskCommand("user-1", "", "key", "input", 1),
        SubmitTaskCommand("user-1", "tender.generate", "", "input", 1),
        SubmitTaskCommand("user-1", "tender.generate", "key", "", 1),
        SubmitTaskCommand("user-1", "tender.generate", "key", "input", 0),
    ],
)
def test_submit_rejects_invalid_domain_identity(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
    command: SubmitTaskCommand,
) -> None:
    service, repository, _ = harness

    with pytest.raises(ValueError):
        service.submit(command)

    assert repository.get(next(iter(repository._tasks), None)) is None


def test_submission_idempotency_returns_original_task_and_rejects_input_conflict(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, _ = harness

    first = _submit(service)
    replay = _submit(service)

    with pytest.raises(TaskIdempotencyConflictError):
        service.submit(
            SubmitTaskCommand(
                owner_subject="user-1",
                task_type="tender.generate",
                idempotency_key="submit-1",
                input_fingerprint="different-input-sha",
                max_attempts=3,
            )
        )

    task = repository.get(first.id)
    assert replay.id == first.id
    assert task is not None
    assert len(task.events) == 1


def test_claim_and_success_submission_are_idempotent(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)

    claimed = _claim(service, submitted.id, clock)
    repeated_claim = _claim(service, submitted.id, clock)
    completed = service.complete(
        CompleteTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="result-sha-1",
            result_summary="已生成合成结果。",
        )
    )
    clock.advance(minutes=10)
    replayed_completion = service.complete(
        CompleteTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="result-sha-1",
            result_summary="已生成合成结果。",
        )
    )

    task = repository.get(submitted.id)
    assert repeated_claim.lease.attempt_id == claimed.lease.attempt_id
    assert completed.status is TaskStatus.SUCCEEDED
    assert replayed_completion.status is TaskStatus.SUCCEEDED
    assert task is not None
    assert len(task.attempts) == 1
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CLAIMED,
        TaskEventType.TASK_SUCCEEDED,
    ]


def test_claim_event_is_the_single_execution_start_fact(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)

    _claim(service, submitted.id, clock)

    task = repository.get(submitted.id)
    assert task is not None
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CLAIMED,
    ]
    assert task.events[-1].metadata == {
        "attempt_number": 1,
        "claim_id": "claim-1",
        "worker_id": "worker-1",
    }


def test_running_cancellation_preserves_attempt_until_executor_confirms(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)

    requested = service.cancel(
        CancelTaskCommand(task_id=submitted.id, command_id="cancel-1")
    )
    replayed_request = service.cancel(
        CancelTaskCommand(task_id=submitted.id, command_id="cancel-1")
    )
    cancelled = service.confirm_cancellation(
        ConfirmCancellationCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
        )
    )

    with pytest.raises(TaskLeaseRejectedError):
        service.complete(
            CompleteTaskCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                result_fingerprint="result-sha-1",
                result_summary="不应写入。",
            )
        )

    task = repository.get(submitted.id)
    assert requested.status is TaskStatus.CANCEL_REQUESTED
    assert replayed_request.status is TaskStatus.CANCEL_REQUESTED
    assert cancelled.status is TaskStatus.CANCELLED
    assert task is not None
    assert task.attempts[0].is_active is False
    assert [event.sequence for event in task.events] == [1, 2, 3, 4]


def test_queued_cancellation_finishes_without_creating_attempt(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, _ = harness
    submitted = _submit(service)

    cancelled = service.cancel(CancelTaskCommand(task_id=submitted.id, command_id="cancel-queued"))

    task = repository.get(submitted.id)
    assert cancelled.status is TaskStatus.CANCELLED
    assert task is not None
    assert task.attempts == []
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CANCELLED,
    ]


def test_transient_failure_requeues_then_manual_retry_is_idempotent(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    first = _claim(service, submitted.id, clock)
    retry_at = clock.now + timedelta(minutes=1)

    waiting = service.fail(
        FailTaskCommand(
            task_id=submitted.id,
            attempt_id=first.lease.attempt_id,
            lease_token=first.lease.lease_token,
            failure_category=FailureCategory.TRANSIENT,
            failure_code="UPSTREAM_TIMEOUT",
            result_fingerprint="failure-sha-1",
            retry_at=retry_at,
        )
    )
    with pytest.raises(TaskStateTransitionError):
        service.requeue_due(RequeueTaskCommand(task_id=submitted.id, command_id="requeue-1"))
    clock.advance(minutes=1)
    queued = service.requeue_due(RequeueTaskCommand(task_id=submitted.id, command_id="requeue-1"))
    second = _claim(service, submitted.id, clock, claim_id="claim-2", lease_token="lease-2")
    failed = service.fail(
        FailTaskCommand(
            task_id=submitted.id,
            attempt_id=second.lease.attempt_id,
            lease_token=second.lease.lease_token,
            failure_category=FailureCategory.PERMANENT,
            failure_code="DOCUMENT_INVALID",
            result_fingerprint="failure-sha-2",
        )
    )
    retried = service.retry(
        RetryTaskCommand(task_id=submitted.id, command_id="manual-retry-1")
    )
    replayed_retry = service.retry(
        RetryTaskCommand(task_id=submitted.id, command_id="manual-retry-1")
    )

    task = repository.get(submitted.id)
    assert waiting.status is TaskStatus.RETRY_WAIT
    assert queued.status is TaskStatus.QUEUED
    assert failed.status is TaskStatus.FAILED
    assert retried.status is TaskStatus.QUEUED
    assert replayed_retry.status is TaskStatus.QUEUED
    assert task is not None
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CLAIMED,
        TaskEventType.TASK_RETRY_SCHEDULED,
        TaskEventType.TASK_REQUEUED,
        TaskEventType.TASK_CLAIMED,
        TaskEventType.TASK_FAILED,
        TaskEventType.TASK_RETRY_REQUESTED,
    ]


def test_renewal_replay_is_stable_and_conflicting_expiry_is_rejected(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, _, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)
    new_expiry = claimed.lease.lease_expires_at + timedelta(minutes=5)

    first = service.renew_lease(
        RenewLeaseCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            renewal_sequence=1,
            lease_expires_at=new_expiry,
        )
    )
    replay = service.renew_lease(
        RenewLeaseCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            renewal_sequence=1,
            lease_expires_at=new_expiry,
        )
    )

    with pytest.raises(TaskIdempotencyConflictError):
        service.renew_lease(
            RenewLeaseCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                renewal_sequence=1,
                lease_expires_at=new_expiry + timedelta(minutes=1),
            )
        )

    assert first.lease.lease_expires_at == new_expiry
    assert replay.lease.renewal_sequence == 1


def test_expired_attempt_cannot_extend_lease(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, _, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)
    clock.advance(minutes=5)

    with pytest.raises(TaskLeaseRejectedError):
        service.renew_lease(
            RenewLeaseCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                renewal_sequence=1,
                lease_expires_at=claimed.lease.lease_expires_at + timedelta(minutes=5),
            )
        )


def test_recovery_expires_old_attempt_and_rejects_late_write(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)
    clock.advance(minutes=5)

    recovered = service.recover(RecoverTaskCommand(task_id=submitted.id, command_id="recover-1"))
    replayed_recovery = service.recover(
        RecoverTaskCommand(task_id=submitted.id, command_id="recover-1")
    )

    with pytest.raises(TaskLeaseRejectedError):
        service.complete(
            CompleteTaskCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                result_fingerprint="late-result-sha",
                result_summary="过期执行结果。",
            )
        )

    second = _claim(service, submitted.id, clock, claim_id="claim-2", lease_token="lease-2")
    task = repository.get(submitted.id)
    assert recovered.status is TaskStatus.QUEUED
    assert replayed_recovery.status is TaskStatus.QUEUED
    assert second.lease.attempt_id != claimed.lease.attempt_id
    assert task is not None
    assert len(task.attempts) == 2
    assert task.events[-2].event_type is TaskEventType.TASK_RECOVERED


def test_recovery_cancels_an_expired_cancel_requested_task(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    _claim(service, submitted.id, clock)
    service.cancel(CancelTaskCommand(task_id=submitted.id, command_id="cancel-1"))
    clock.advance(minutes=5)

    recovered = service.recover(RecoverTaskCommand(task_id=submitted.id, command_id="recover-1"))

    task = repository.get(submitted.id)
    assert recovered.status is TaskStatus.CANCELLED
    assert task is not None
    assert task.attempts[0].is_active is False
    assert task.events[-1].event_type is TaskEventType.TASK_RECOVERED
    assert task.events[-1].metadata["outcome"] == TaskStatus.CANCELLED.value


def test_terminal_state_rejects_new_command_without_writing_event(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)
    service.complete(
        CompleteTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="result-sha-1",
            result_summary="已完成。",
        )
    )
    task = repository.get(submitted.id)
    assert task is not None
    event_count = len(task.events)

    with pytest.raises(TaskStateTransitionError):
        service.cancel(CancelTaskCommand(task_id=submitted.id, command_id="cancel-after-success"))

    assert len(task.events) == event_count
    assert task.status is TaskStatus.SUCCEEDED


@pytest.mark.parametrize(
    ("event_type", "metadata", "message"),
    [
        (TaskEventType.TASK_CREATED, {"lease_token": "do-not-store"}, "敏感"),
        (TaskEventType.TASK_CREATED, {"unexpected": "value"}, "不允许"),
        (TaskEventType.TASK_CLAIMED, {"attempt_number": math.nan}, "非有限"),
        (
            TaskEventType.TASK_FAILED,
            {
                "attempt_number": 1,
                "failure_category": "permanent",
                "failure_code": "Traceback from provider",
            },
            "安全分类",
        ),
    ],
)
def test_events_reject_unsafe_or_nonstandard_metadata(
    event_type: TaskEventType,
    metadata: dict[str, object],
    message: str,
) -> None:
    now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match=message):
        TaskEvent(
            task_id=uuid4(),
            sequence=1,
            transition_id="transition-1",
            event_type=event_type,
            metadata=metadata,
            created_at=now,
        )


def test_terminal_submissions_reject_unsafe_codes_and_fingerprints(
    harness: tuple[TaskLifecycleService, InMemoryTaskRepository, MutableClock],
) -> None:
    service, repository, clock = harness
    submitted = _submit(service)
    claimed = _claim(service, submitted.id, clock)

    with pytest.raises(ValueError, match="结果指纹"):
        service.complete(
            CompleteTaskCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                result_fingerprint="raw provider response",
                result_summary="不应写入。",
            )
        )
    with pytest.raises(ValueError, match="失败码"):
        service.fail(
            FailTaskCommand(
                task_id=submitted.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                failure_category=FailureCategory.PERMANENT,
                failure_code="Traceback from provider",
                result_fingerprint="failure-sha-1",
            )
        )

    task = repository.get(submitted.id)
    assert task is not None
    assert task.status is TaskStatus.RUNNING
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CLAIMED,
    ]
