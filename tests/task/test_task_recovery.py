from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.platform.task.application import (
    CancellationCheckCommand,
    CancellationCoordinator,
    ManualRetryCoordinator,
    RecoveryCoordinator,
    RetryScheduler,
    SubmitTaskCommand,
    TaskLifecycleService,
)
from app.platform.task.application.contracts import (
    CancelTaskCommand,
    RecoverTaskCommand,
    RetryTaskCommand,
)
from app.platform.task.application.executor_contracts import (
    ClaimTaskCommand,
    ConfirmCancellationCommand,
    FailTaskCommand,
)
from app.platform.task.domain import FailureCategory, TaskEventType, TaskStatus
from tests.task.in_memory_repository import InMemoryTaskRepository


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: int) -> None:
        self.now += timedelta(**delta)


def _submit(service: TaskLifecycleService, *, key: str, max_attempts: int = 3):
    return service.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="demo.execute",
            idempotency_key=key,
            input_fingerprint=f"fingerprint-{key}",
            max_attempts=max_attempts,
        )
    )


def _claim(service: TaskLifecycleService, task_id, clock: MutableClock, claim_id: str = "claim-1"):
    return service.claim(
        ClaimTaskCommand(
            task_id=task_id,
            worker_id="worker-1",
            claim_id=claim_id,
            lease_token=f"lease-{claim_id}",
            lease_expires_at=clock.now + timedelta(minutes=5),
        )
    )


def test_recovery_coordinator_scans_expired_attempt_and_uses_stable_command() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="recover-1")
    _claim(lifecycle, submitted.id, clock)
    clock.advance(minutes=5)

    coordinator = RecoveryCoordinator(repository, lifecycle, clock=clock)
    first = coordinator.run_once()
    second = coordinator.run_once()

    assert first[0].status == TaskStatus.QUEUED.value
    assert first[0].error_code is None
    assert second == []
    task = repository.get(submitted.id)
    assert task is not None
    assert [event.event_type for event in task.events].count(TaskEventType.TASK_RECOVERED) == 1


def test_recovery_coordinator_keeps_cancel_requested_task_cancelled() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="recover-cancel")
    claimed = _claim(lifecycle, submitted.id, clock)
    lifecycle.cancel(CancelTaskCommand(task_id=submitted.id, command_id="cancel-1"))
    clock.advance(minutes=5)

    result = RecoveryCoordinator(repository, lifecycle, clock=clock).run_once()[0]

    assert result.status == TaskStatus.CANCELLED.value
    assert repository.get(submitted.id).attempts[0].is_active is False  # type: ignore[union-attr]
    assert claimed.lease.lease_token not in str(result)


def test_recovery_coordinator_fails_task_when_attempts_are_exhausted() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="recover-exhausted", max_attempts=1)
    _claim(lifecycle, submitted.id, clock)
    clock.advance(minutes=5)

    result = RecoveryCoordinator(repository, lifecycle, clock=clock).run_once()[0]

    assert result.status == TaskStatus.FAILED.value
    task = repository.get(submitted.id)
    assert task is not None
    assert task.failure_code == "LEASE_EXPIRED"
    assert task.attempts[0].lease_token not in task.events[-1].metadata


def test_recovery_coordinator_can_apply_explicit_retry_delay() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="recover-delay")
    _claim(lifecycle, submitted.id, clock)
    clock.advance(minutes=5)

    result = RecoveryCoordinator(
        repository,
        lifecycle,
        clock=clock,
        retry_delay=timedelta(minutes=2),
    ).run_once()[0]

    assert result.status == TaskStatus.RETRY_WAIT.value
    assert repository.get(submitted.id).available_at == clock.now + timedelta(minutes=2)  # type: ignore[union-attr]


def test_retry_scheduler_only_requeues_due_retry_wait() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="retry-1")
    claimed = _claim(lifecycle, submitted.id, clock)
    lifecycle.fail(
        FailTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            failure_category=FailureCategory.TRANSIENT,
            failure_code="UPSTREAM_TIMEOUT",
            result_fingerprint="failure-1",
            retry_at=clock.now + timedelta(minutes=1),
        )
    )
    scheduler = RetryScheduler(repository, lifecycle, clock=clock)

    assert scheduler.run_once() == []
    clock.advance(minutes=1)
    result = scheduler.run_once()[0]

    assert result.status == TaskStatus.QUEUED.value
    assert repository.get(submitted.id).events[-1].event_type is TaskEventType.TASK_REQUEUED  # type: ignore[union-attr]


def test_cancellation_coordinator_requires_executor_confirmation() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="cancel-1")
    claimed = _claim(lifecycle, submitted.id, clock)
    coordinator = CancellationCoordinator(lifecycle)

    requested = coordinator.request(task_id=submitted.id, command_id="cancel-1")
    assert requested.status == TaskStatus.CANCEL_REQUESTED.value
    assert lifecycle.is_cancel_requested(
        CancellationCheckCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
        )
    ) is True

    confirmed = coordinator.confirm(
        ConfirmCancellationCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
        )
    )
    assert confirmed.status == TaskStatus.CANCELLED.value


def test_manual_retry_coordinator_returns_safe_policy_error_without_sensitive_data() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="retry-policy", max_attempts=1)
    claimed = _claim(lifecycle, submitted.id, clock)
    lifecycle.fail(
        FailTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token="lease-claim-1",
            failure_category=FailureCategory.PERMANENT,
            failure_code="PROVIDER_FAILED",
            result_fingerprint="failure-policy",
        )
    )

    result = ManualRetryCoordinator(lifecycle).retry(
        RetryTaskCommand(task_id=submitted.id, command_id="manual-retry-1")
    )

    assert result.status is None
    assert result.error_code == "CANDIDATE_NOT_APPLICABLE"
    assert "lease-claim-1" not in str(result)
    assert repository.get(submitted.id).status is TaskStatus.FAILED  # type: ignore[union-attr]


def test_recovery_command_replay_returns_current_state_without_new_event() -> None:
    clock = MutableClock()
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(lifecycle, key="replay-1")
    _claim(lifecycle, submitted.id, clock)
    clock.advance(minutes=5)

    first = lifecycle.recover(
        RecoverTaskCommand(task_id=submitted.id, command_id="recover-fixed")
    )
    event_count = len(repository.get(submitted.id).events)  # type: ignore[union-attr]
    replay = lifecycle.recover(
        RecoverTaskCommand(task_id=submitted.id, command_id="recover-fixed")
    )

    assert replay.status is first.status
    assert len(repository.get(submitted.id).events) == event_count  # type: ignore[union-attr]
