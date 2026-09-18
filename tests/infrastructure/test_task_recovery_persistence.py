from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.task.application import (
    RecoveryCoordinator,
    RetryScheduler,
    SubmitTaskCommand,
    TaskLifecycleService,
)
from app.platform.task.application.executor_contracts import ClaimTaskCommand, FailTaskCommand
from app.platform.task.domain import FailureCategory, TaskEventType, TaskStatus
from tests.support.db_test_utils import SchemaHarness


class MutableClock:
    now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def _submit(session, clock: MutableClock, key: str):  # noqa: ANN001
    return TaskLifecycleService(PostgresTaskRepository(session), clock=clock).submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="demo.execute",
            idempotency_key=key,
            input_fingerprint=f"fingerprint-{key}",
            max_attempts=3,
        )
    )


def _expire_task(session, clock: MutableClock, key: str):  # noqa: ANN001
    service = TaskLifecycleService(PostgresTaskRepository(session), clock=clock)
    submitted = _submit(session, clock, key)
    claimed = service.claim(
        ClaimTaskCommand(
            task_id=submitted.id,
            worker_id="worker-1",
            claim_id="claim-1",
            lease_token="lease-1",
            lease_expires_at=clock.now + timedelta(minutes=5),
        )
    )
    clock.now += timedelta(minutes=5)
    return submitted, claimed


def test_postgres_recovery_candidates_are_locked_and_unique() -> None:
    harness = SchemaHarness("task_recovery_concurrency")
    harness.create_schema()
    clock = MutableClock()
    try:
        seed_session = harness.session_local()
        try:
            submitted, _ = _expire_task(seed_session, clock, "recovery-concurrent")
        finally:
            seed_session.close()

        def recover_once():
            session = harness.session_local()
            try:
                repository = PostgresTaskRepository(session)
                lifecycle = TaskLifecycleService(repository, clock=clock)
                return RecoveryCoordinator(repository, lifecycle, clock=clock).run_once()
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(lambda _: recover_once(), range(2)))

        assert sorted(len(batch) for batch in batches) == [0, 1]
        restored_session = harness.session_local()
        try:
            restored = PostgresTaskRepository(restored_session).get(submitted.id)
            assert restored is not None
            assert restored.status is TaskStatus.QUEUED
            assert [event.event_type for event in restored.events].count(
                TaskEventType.TASK_RECOVERED
            ) == 1
        finally:
            restored_session.close()
    finally:
        harness.drop_schema()


def test_postgres_retry_scheduler_skips_future_retry_and_requeues_due_task() -> None:
    harness = SchemaHarness("task_retry_scheduler")
    harness.create_schema()
    clock = MutableClock()
    try:
        session = harness.session_local()
        try:
            service = TaskLifecycleService(PostgresTaskRepository(session), clock=clock)
            submitted = _submit(session, clock, "retry-scheduled")
            claimed = service.claim(
                ClaimTaskCommand(
                    task_id=submitted.id,
                    worker_id="worker-1",
                    claim_id="claim-1",
                    lease_token="lease-1",
                    lease_expires_at=clock.now + timedelta(minutes=5),
                )
            )
            service.fail(
                FailTaskCommand(
                    task_id=submitted.id,
                    attempt_id=claimed.lease.attempt_id,
                    lease_token="lease-1",
                    failure_category=FailureCategory.TRANSIENT,
                    failure_code="UPSTREAM_TIMEOUT",
                    result_fingerprint="failure-1",
                    retry_at=clock.now + timedelta(minutes=1),
                )
            )
            repository = PostgresTaskRepository(session)
            scheduler = RetryScheduler(
                repository,
                TaskLifecycleService(repository, clock=clock),
                clock=clock,
            )
            assert scheduler.run_once() == []
            clock.now += timedelta(minutes=1)
            result = scheduler.run_once()
            assert result[0].status == TaskStatus.QUEUED.value
        finally:
            session.close()
    finally:
        harness.drop_schema()
