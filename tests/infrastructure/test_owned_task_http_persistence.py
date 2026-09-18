from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.security import RequestPrincipal
from app.platform.task.application import (
    CancellationCoordinator,
    ManualRetryCoordinator,
    OwnedTaskApplication,
    OwnedTaskCommand,
    OwnedTaskEventsQuery,
    OwnedTaskListQuery,
    OwnedTaskQuery,
    SubmitTaskCommand,
    TaskLifecycleService,
)
from app.platform.task.application.executor_contracts import ClaimTaskCommand
from app.platform.task.domain import TaskEvent, TaskEventType
from app.platform.task.ports import TaskCommandReceipt
from tests.support.db_test_utils import SchemaHarness


def test_postgres_owned_task_reads_filter_owner_and_page_events() -> None:
    harness = SchemaHarness("task_owned_http")
    harness.create_schema()
    clock = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
    try:
        session = harness.session_local()
        try:
            lifecycle = TaskLifecycleService(
                PostgresTaskRepository(session), clock=lambda: clock
            )
            task = lifecycle.submit(
                SubmitTaskCommand("owner-1", "demo.execute", "owned-1", "input-1", 2)
            )
            lifecycle.submit(
                SubmitTaskCommand("owner-2", "demo.execute", "owned-2", "input-2", 2)
            )
            claimed = lifecycle.claim(
                ClaimTaskCommand(
                    task_id=task.id,
                    worker_id="worker-1",
                    claim_id="claim-1",
                    lease_token="lease-1",
                    lease_expires_at=clock + timedelta(minutes=5),
                )
            )
            repository = PostgresTaskRepository(session)
            application = OwnedTaskApplication(
                repository,
                CancellationCoordinator(lifecycle),
                ManualRetryCoordinator(lifecycle),
            )
            principal = RequestPrincipal(subject="owner-1", authenticated=True)

            page = application.list_owned(OwnedTaskListQuery(principal, limit=10))
            events = application.read_events(
                OwnedTaskEventsQuery(principal, task.id, limit=1)
            )

            assert [item.id for item in page.tasks] == [task.id]
            assert [event.sequence for event in events.events] == [1]
            assert events.has_more is True
            assert application.get_owned(OwnedTaskQuery(principal, task.id)).id == task.id
            assert claimed.lease.lease_token not in str(events)
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_postgres_owned_task_commands_replay_across_independent_sessions() -> None:
    harness = SchemaHarness("task_owned_http_commands")
    harness.create_schema()
    try:
        seed_session = harness.session_local()
        try:
            lifecycle = TaskLifecycleService(
                PostgresTaskRepository(seed_session),
                clock=lambda: datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
            )
            task = lifecycle.submit(
                SubmitTaskCommand("owner-1", "demo.execute", "command-1", "input-1", 2)
            )
        finally:
            seed_session.close()

        owner_session = harness.session_local()
        try:
            repository = PostgresTaskRepository(owner_session)
            lifecycle = TaskLifecycleService(repository)
            application = OwnedTaskApplication(
                repository,
                CancellationCoordinator(lifecycle),
                ManualRetryCoordinator(lifecycle),
            )
            principal = RequestPrincipal(subject="owner-1", authenticated=True)
            first = application.cancel(
                OwnedTaskCommand(principal, task.id, "cancel-http-1")
            )
            assert first.task is not None
        finally:
            owner_session.close()

        replay_session = harness.session_local()
        try:
            repository = PostgresTaskRepository(replay_session)
            lifecycle = TaskLifecycleService(repository)
            application = OwnedTaskApplication(
                repository,
                CancellationCoordinator(lifecycle),
                ManualRetryCoordinator(lifecycle),
            )
            principal = RequestPrincipal(subject="owner-1", authenticated=True)
            replay = application.cancel(
                OwnedTaskCommand(principal, task.id, "cancel-http-1")
            )
            restored = repository.get(task.id)
            assert replay.task is not None
            assert replay.task.status.value == "cancelled"
            assert restored is not None
            assert len(restored.events) == 2
            assert repository.has_processed_command(
                task_id=task.id, command_type="cancel", command_id="cancel-http-1"
            )
        finally:
            replay_session.close()
    finally:
        harness.drop_schema()


def test_postgres_owned_task_save_rolls_back_attempt_event_and_receipt_together() -> None:
    harness = SchemaHarness("task_owned_http_rollback")
    harness.create_schema()
    clock = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
    try:
        session = harness.session_local()
        try:
            lifecycle = TaskLifecycleService(PostgresTaskRepository(session), clock=lambda: clock)
            submitted = lifecycle.submit(
                SubmitTaskCommand("owner-1", "demo.execute", "rollback-1", "input-1", 2)
            )
            repository = PostgresTaskRepository(session)
            task = repository.get_for_update(submitted.id)
            assert task is not None
            task.claim(
                worker_id="worker-1",
                claim_id="claim-1",
                lease_token="lease-1",
                lease_expires_at=clock + timedelta(minutes=5),
                now=clock,
            )
            task.events.append(
                TaskEvent(
                    task_id=task.id,
                    sequence=1,
                    transition_id="duplicate",
                    event_type=TaskEventType.TASK_CLAIMED,
                    metadata={
                        "attempt_number": 1,
                        "claim_id": "duplicate",
                        "worker_id": "worker-1",
                    },
                    created_at=clock,
                )
            )

            with pytest.raises(IntegrityError):
                repository.save(
                    task,
                    command_receipt=TaskCommandReceipt(task.id, "cancel", "rollback-command"),
                )

            restored = repository.get(submitted.id)
            assert restored is not None
            assert restored.status.value == "queued"
            assert restored.attempts == []
            assert len(restored.events) == 1
            assert not repository.has_processed_command(
                task_id=submitted.id,
                command_type="cancel",
                command_id="rollback-command",
            )
        finally:
            session.close()
    finally:
        harness.drop_schema()
