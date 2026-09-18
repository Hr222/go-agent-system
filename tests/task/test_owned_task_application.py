from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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
from app.platform.task.errors import TaskAccessDeniedError, TaskUnavailableError
from tests.task.in_memory_repository import InMemoryTaskRepository


def _app() -> tuple[OwnedTaskApplication, TaskLifecycleService, InMemoryTaskRepository]:
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    return (
        OwnedTaskApplication(
            repository,
            CancellationCoordinator(lifecycle),
            ManualRetryCoordinator(lifecycle),
        ),
        lifecycle,
        repository,
    )


def _principal(subject: str, authenticated: bool = True) -> RequestPrincipal:
    return RequestPrincipal(subject=subject, authenticated=authenticated)


def test_owned_application_filters_list_and_events_and_keeps_projection_safe() -> None:
    application, lifecycle, repository = _app()
    first = lifecycle.submit(
        SubmitTaskCommand("owner-1", "demo.execute", "key-1", "input-1", 2)
    )
    lifecycle.submit(SubmitTaskCommand("owner-2", "demo.execute", "key-2", "input-2", 2))

    page = application.list_owned(OwnedTaskListQuery(_principal("owner-1"), limit=10))
    events = application.read_events(
        OwnedTaskEventsQuery(_principal("owner-1"), first.id, limit=10)
    )

    assert [task.id for task in page.tasks] == [first.id]
    assert events.events[0].event_type == "TASK_CREATED"
    assert "input_fingerprint" not in events.events[0].metadata
    assert "lease_token" not in str(events)
    assert repository.get_owned(task_id=first.id, owner_subject="owner-2") is None


def test_owned_application_rejects_cross_subject_and_anonymous_access() -> None:
    application, lifecycle, _ = _app()
    task = lifecycle.submit(
        SubmitTaskCommand("owner-1", "demo.execute", "key-1", "input-1", 2)
    )

    with pytest.raises(TaskUnavailableError):
        application.get_owned(OwnedTaskQuery(_principal("owner-2"), task.id))
    with pytest.raises(TaskAccessDeniedError):
        application.list_owned(OwnedTaskListQuery(_principal("owner-1", False), limit=10))


def test_owned_application_cancel_is_idempotent_and_requires_owner() -> None:
    application, lifecycle, repository = _app()
    task = lifecycle.submit(
        SubmitTaskCommand("owner-1", "demo.execute", "key-1", "input-1", 2)
    )

    first = application.cancel(
        OwnedTaskCommand(_principal("owner-1"), task.id, "cancel-1")
    )
    replay = application.cancel(
        OwnedTaskCommand(_principal("owner-1"), task.id, "cancel-1")
    )

    assert first.task is not None and first.task.status.value == "cancelled"
    assert replay.task is not None and replay.task.status.value == "cancelled"
    assert len(repository.get(task.id).events) == 2  # type: ignore[union-attr]


def test_owned_application_reads_ordered_events_after_sequence() -> None:
    application, lifecycle, _ = _app()
    task = lifecycle.submit(
        SubmitTaskCommand("owner-1", "demo.execute", "key-1", "input-1", 2)
    )
    lifecycle.claim(
        ClaimTaskCommand(
            task_id=task.id,
            worker_id="worker-1",
            claim_id="claim-1",
            lease_token="lease-1",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    page = application.read_events(
        OwnedTaskEventsQuery(_principal("owner-1"), task.id, limit=1, after_sequence=1)
    )
    assert [event.sequence for event in page.events] == [2]
