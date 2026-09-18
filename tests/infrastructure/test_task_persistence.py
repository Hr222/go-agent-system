from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.persistence.models.task import (
    TaskAttemptRecord,
    TaskEventRecord,
    TaskRecord,
)
from app.infrastructure.persistence.repositories.task_repository import (
    PostgresTaskRepository,
)
from app.platform.security.domain import RequestPrincipal
from app.platform.task.application import (
    CancelTaskCommand,
    SubmitTaskCommand,
    TaskLifecycleService,
    TrustedTaskSubmissionCommand,
    TrustedTaskSubmissionProfile,
    TrustedTaskSubmissionService,
)
from app.platform.task.application.executor_contracts import ClaimTaskCommand
from app.platform.task.domain import TaskEvent, TaskEventType, TaskStatus
from app.platform.task.errors import TaskSchemaUnavailableError, TaskSubmissionPrincipalError
from tests.support.db_test_utils import SchemaHarness

SQL_SCRIPT = Path(__file__).resolve().parents[2] / "sql" / "013_task_lifecycle.sql"


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def _submit(service: TaskLifecycleService):
    return service.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="tender.generate",
            idempotency_key="submit-1",
            input_fingerprint="input-sha-1",
            max_attempts=3,
            display_metadata={"title": "持久化任务"},
        )
    )


def test_task_sql_script_is_idempotent_and_creates_all_tables() -> None:
    harness = SchemaHarness("task_sql")
    with harness.admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{harness.schema}"'))
    try:
        script = SQL_SCRIPT.read_text(encoding="utf-8")
        with harness.test_engine.begin() as connection:
            connection.exec_driver_sql(script)
            connection.exec_driver_sql(script)
            tables = set(
                connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                        "AND tablename LIKE 'task%'"
                    )
                ).scalars()
            )
        assert tables == {
            "task",
            "task_attempt",
            "task_event",
            "task_command_receipt",
        }
        assert "CREATE TABLE IF NOT EXISTS task" in script
        assert "uq_task_submission" in script
        assert "uq_task_attempt_one_active" in script
    finally:
        harness.drop_schema()


def test_task_repository_persists_and_restores_the_full_aggregate() -> None:
    harness = SchemaHarness("task_persist")
    harness.create_schema()
    clock = MutableClock()
    try:
        session = harness.session_local()
        try:
            service = TaskLifecycleService(PostgresTaskRepository(session), clock=clock)
            submitted = _submit(service)
            claimed = service.claim(
                ClaimTaskCommand(
                    task_id=submitted.id,
                    worker_id="worker-1",
                    claim_id="claim-1",
                    lease_token="lease-1",
                    lease_expires_at=clock.now + timedelta(minutes=5),
                )
            )
            task_id = submitted.id
            attempt_id = claimed.lease.attempt_id
        finally:
            session.close()

        restored_session = harness.session_local()
        try:
            restored = PostgresTaskRepository(restored_session).get(task_id)
            assert restored is not None
            assert restored.status is TaskStatus.RUNNING
            assert restored.attempts[0].id == attempt_id
            assert [event.event_type for event in restored.events] == [
                TaskEventType.TASK_CREATED,
                TaskEventType.TASK_CLAIMED,
            ]
            assert restored.attempts[0].lease_token == "lease-1"
            assert "lease_token" not in restored.events[-1].metadata
        finally:
            restored_session.close()
    finally:
        harness.drop_schema()


def test_task_command_receipt_survives_repository_restart() -> None:
    harness = SchemaHarness("task_receipt")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = TaskLifecycleService(PostgresTaskRepository(session), clock=MutableClock())
            submitted = _submit(service)
            first = service.cancel(CancelTaskCommand(submitted.id, "cancel-1"))
        finally:
            session.close()

        replay_session = harness.session_local()
        try:
            replay_service = TaskLifecycleService(
                PostgresTaskRepository(replay_session), clock=MutableClock()
            )
            replayed = replay_service.cancel(CancelTaskCommand(submitted.id, "cancel-1"))
            restored = PostgresTaskRepository(replay_session).get(submitted.id)
            assert first.status is TaskStatus.CANCELLED
            assert replayed.status is TaskStatus.CANCELLED
            assert restored is not None
            assert len(restored.events) == 2
            assert PostgresTaskRepository(replay_session).has_processed_command(
                task_id=submitted.id, command_type="cancel", command_id="cancel-1"
            )
            repository = PostgresTaskRepository(replay_session)
            repository.mark_command_processed(
                task_id=submitted.id, command_type="cancel", command_id="cancel-1"
            )
            repository.mark_command_processed(
                task_id=submitted.id, command_type="cancel", command_id="cancel-1"
            )
        finally:
            replay_session.close()
    finally:
        harness.drop_schema()


def test_database_rejects_second_active_attempt_and_orphan_event() -> None:
    harness = SchemaHarness("task_constraints")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            task_id = uuid4()
            now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
            session.add(
                TaskRecord(
                    id=task_id,
                    task_type="demo",
                    owner_subject="owner-1",
                    idempotency_key="key-1",
                    input_fingerprint="input-1",
                    max_attempts=2,
                    available_at=now,
                    status="running",
                    display_metadata={},
                    allow_manual_retry=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            session.add(
                TaskAttemptRecord(
                    id=uuid4(), task_id=task_id, number=1, worker_id="worker-1",
                    claim_id="claim-1", lease_token="lease-1",
                    lease_expires_at=now + timedelta(minutes=5), status="active",
                    renewal_sequence=0, created_at=now,
                )
            )
            session.commit()
            session.add(
                TaskAttemptRecord(
                    id=uuid4(), task_id=task_id, number=2, worker_id="worker-2",
                    claim_id="claim-2", lease_token="lease-2",
                    lease_expires_at=now + timedelta(minutes=5), status="active",
                    renewal_sequence=0, created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(TaskAttemptRecord).count() == 1

            session.add(
                TaskAttemptRecord(
                    id=uuid4(), task_id=task_id, number=1, worker_id="worker-3",
                    claim_id="claim-3", lease_token="lease-3",
                    lease_expires_at=now + timedelta(minutes=5), status="failed",
                    renewal_sequence=0, created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(TaskAttemptRecord).count() == 1

            existing_event = TaskEventRecord(
                id=uuid4(), task_id=task_id, sequence=1, transition_id="transition-1",
                event_type="TASK_CREATED", event_metadata={}, created_at=now,
            )
            session.add(existing_event)
            session.commit()
            session.add(
                TaskEventRecord(
                    id=uuid4(), task_id=task_id, sequence=1, transition_id="transition-2",
                    event_type="TASK_CLAIMED", event_metadata={}, created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(TaskEventRecord).count() == 1

            session.add(
                TaskEventRecord(
                    id=uuid4(), task_id=task_id, sequence=2, transition_id="transition-1",
                    event_type="TASK_CLAIMED", event_metadata={}, created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(TaskEventRecord).count() == 1

            session.add(
                TaskEventRecord(
                    id=uuid4(), task_id=uuid4(), sequence=1, transition_id="orphan",
                    event_type="TASK_CREATED", event_metadata={}, created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            assert session.query(TaskEventRecord).count() == 1
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_repository_rolls_back_task_attempt_and_event_together() -> None:
    harness = SchemaHarness("task_rollback")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            service = TaskLifecycleService(PostgresTaskRepository(session), clock=MutableClock())
            submitted = _submit(service)
            task = PostgresTaskRepository(session).get_for_update(submitted.id)
            assert task is not None
            task.claim(
                worker_id="worker-1",
                claim_id="claim-1",
                lease_token="lease-1",
                lease_expires_at=datetime(2026, 9, 18, 9, 5, tzinfo=timezone.utc),
                now=datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
            )
            task.events.append(
                TaskEvent(
                    task_id=task.id,
                    sequence=3,
                    transition_id=task.events[0].transition_id,
                    event_type=TaskEventType.TASK_CLAIMED,
                    metadata={
                        "attempt_number": 1,
                        "claim_id": "duplicate",
                        "worker_id": "worker-1",
                    },
                    created_at=datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
                )
            )
            with pytest.raises(IntegrityError):
                PostgresTaskRepository(session).save(task)

            restored = PostgresTaskRepository(session).get(submitted.id)
            assert restored is not None
            assert restored.status is TaskStatus.QUEUED
            assert restored.attempts == []
            assert len(restored.events) == 1
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_concurrent_same_submission_and_claim_are_serialized() -> None:
    harness = SchemaHarness("task_concurrency")
    harness.create_schema()
    try:
        clock = MutableClock()
        seed_session = harness.session_local()
        try:
            seed_service = TaskLifecycleService(PostgresTaskRepository(seed_session), clock=clock)
            submitted = _submit(seed_service)
        finally:
            seed_session.close()

        def submit_in_new_session():
            session = harness.session_local()
            try:
                return _submit(TaskLifecycleService(PostgresTaskRepository(session), clock=clock))
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit_in_new_session(), range(2)))
        assert {result.id for result in results} == {submitted.id}

        def claim_in_new_session():
            session = harness.session_local()
            try:
                return TaskLifecycleService(PostgresTaskRepository(session), clock=clock).claim(
                    ClaimTaskCommand(
                        task_id=submitted.id,
                        worker_id="worker-1",
                        claim_id="claim-concurrent",
                        lease_token="lease-concurrent",
                        lease_expires_at=clock.now + timedelta(minutes=5),
                    )
                )
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(claim_in_new_session) for _ in range(2)]
            successes = []
            failures = []
            for future in futures:
                try:
                    successes.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    failures.append(exc)
        assert len(successes) == 2
        assert successes[0].lease.attempt_id == successes[1].lease.attempt_id
        assert failures == []
    finally:
        harness.drop_schema()


def test_missing_task_schema_has_actionable_error() -> None:
    harness = SchemaHarness("task_missing_schema")
    with harness.admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{harness.schema}"'))
    try:
        session = harness.session_local()
        try:
            with pytest.raises(TaskSchemaUnavailableError, match="013_task_lifecycle"):
                PostgresTaskRepository(session).get(uuid4())
            assert session.is_active
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_trusted_submission_replays_after_repository_restart_and_rejects_untrusted_input() -> None:
    harness = SchemaHarness("task_trusted_submit")
    harness.create_schema()
    profile = TrustedTaskSubmissionProfile(
        task_type="tender.generate",
        max_attempts=2,
        allow_manual_retry=False,
        display_metadata_fields=("title",),
    )
    principal = RequestPrincipal(subject="owner-1", authenticated=True)
    command = TrustedTaskSubmissionCommand(
        idempotency_key="submit-1",
        input_fingerprint="input-sha-1",
        display_metadata={"title": "持久化任务"},
    )
    try:
        session = harness.session_local()
        try:
            first = TrustedTaskSubmissionService(
                TaskLifecycleService(PostgresTaskRepository(session), clock=MutableClock()),
                profile,
            ).submit(principal, command)
        finally:
            session.close()

        replay_session = harness.session_local()
        try:
            replay = TrustedTaskSubmissionService(
                TaskLifecycleService(PostgresTaskRepository(replay_session), clock=MutableClock()),
                profile,
            ).submit(principal, command)
            restored = PostgresTaskRepository(replay_session).get(first.id)
            assert replay.id == first.id
            assert restored is not None
            assert len(restored.events) == 1
            with pytest.raises(TaskSubmissionPrincipalError):
                TrustedTaskSubmissionService(
                    TaskLifecycleService(
                        PostgresTaskRepository(replay_session), clock=MutableClock()
                    ),
                    profile,
                ).submit(
                    RequestPrincipal.anonymous(),
                    TrustedTaskSubmissionCommand("submit-2", "input-sha-2"),
                )
            assert PostgresTaskRepository(replay_session).get(first.id) is not None
        finally:
            replay_session.close()
    finally:
        harness.drop_schema()
