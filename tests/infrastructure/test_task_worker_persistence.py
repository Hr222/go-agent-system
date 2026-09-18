from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.task.application import (
    MappingTaskExecutorRegistry,
    SecureLeaseIssuer,
    SubmitTaskCommand,
    TaskLifecycleService,
    TaskWorker,
    WorkerPollStatus,
)
from app.platform.task.ports.worker import TaskExecutionContext, TaskExecutionSuccess
from tests.support.db_test_utils import SchemaHarness


class SuccessExecutor:
    def execute(self, context: TaskExecutionContext) -> TaskExecutionSuccess:
        return TaskExecutionSuccess(
            result_fingerprint="postgres-result-1",
            result_summary="PostgreSQL 执行完成",
        )


class MutableClock:
    now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def _submit(session, clock: MutableClock):  # noqa: ANN001
    return TaskLifecycleService(PostgresTaskRepository(session), clock=clock).submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="demo.execute",
            idempotency_key="postgres-worker-1",
            input_fingerprint="postgres-input-1",
            max_attempts=2,
        )
    )


def test_postgres_worker_claims_one_task_across_independent_sessions() -> None:
    harness = SchemaHarness("task_worker_concurrency")
    harness.create_schema()
    clock = MutableClock()
    try:
        seed_session = harness.session_local()
        try:
            submitted = _submit(seed_session, clock)
        finally:
            seed_session.close()

        def poll(worker_id: str):
            session = harness.session_local()
            try:
                repository = PostgresTaskRepository(session)
                return TaskWorker(
                    repository=repository,
                    lifecycle=TaskLifecycleService(repository, clock=clock),
                    executors=MappingTaskExecutorRegistry({"demo.execute": SuccessExecutor()}),
                    lease_issuer=SecureLeaseIssuer(
                        ttl=timedelta(minutes=5),
                        token_factory=lambda: f"lease-{worker_id}",
                    ),
                    worker_id=worker_id,
                    clock=clock,
                ).poll_once()
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(poll, ["worker-1", "worker-2"]))

        assert sorted(result.status.value for result in results) == ["idle", "succeeded"]
        restored_session = harness.session_local()
        try:
            restored = PostgresTaskRepository(restored_session).get(submitted.id)
            assert restored is not None
            assert len(restored.attempts) == 1
            assert [event.event_type.value for event in restored.events].count("TASK_CLAIMED") == 1
            assert restored.status.value == "succeeded"
        finally:
            restored_session.close()
    finally:
        harness.drop_schema()


def test_postgres_worker_skips_task_before_available_time() -> None:
    harness = SchemaHarness("task_worker_schedule")
    harness.create_schema()
    clock = MutableClock()
    try:
        session = harness.session_local()
        try:
            submitted = _submit(session, clock)
            task = PostgresTaskRepository(session).get_for_update(submitted.id)
            assert task is not None
            task.available_at = clock.now + timedelta(minutes=10)
            task.updated_at = clock.now
            PostgresTaskRepository(session).save(task)
            result = TaskWorker(
                repository=PostgresTaskRepository(session),
                lifecycle=TaskLifecycleService(PostgresTaskRepository(session), clock=clock),
                executors=MappingTaskExecutorRegistry({"demo.execute": SuccessExecutor()}),
                lease_issuer=SecureLeaseIssuer(token_factory=lambda: "lease-future"),
                worker_id="worker-1",
                clock=clock,
            ).poll_once()
            assert result.status is WorkerPollStatus.IDLE
        finally:
            session.close()
    finally:
        harness.drop_schema()
