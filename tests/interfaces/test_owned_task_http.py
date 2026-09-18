from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_owned_task_application,
)
from app.interfaces.http.routes.tasks import router
from app.interfaces.http.security import get_request_principal
from app.platform.security import RequestPrincipal
from app.platform.task.application import (
    CancellationCoordinator,
    ManualRetryCoordinator,
    OwnedTaskApplication,
    SubmitTaskCommand,
    TaskLifecycleService,
)
from app.platform.task.application.executor_contracts import ClaimTaskCommand, FailTaskCommand
from app.platform.task.domain import FailureCategory, Task
from tests.task.in_memory_repository import InMemoryTaskRepository


def _client(subject: str | None) -> tuple[TestClient, OwnedTaskApplication, object]:
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    application = OwnedTaskApplication(
        repository,
        CancellationCoordinator(lifecycle),
        ManualRetryCoordinator(lifecycle),
    )
    principal = RequestPrincipal(
        subject=subject,
        authenticated=subject is not None,
    )
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/tasks")
    test_app.dependency_overrides[get_owned_task_application] = lambda: application
    test_app.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(test_app), application, repository


def test_task_http_list_and_detail_are_owner_scoped_and_safe() -> None:
    client, application, _ = _client("owner-1")
    task = application._repository.create_or_get_submission(  # noqa: SLF001
        Task.create(
        task_type="demo.execute",
        owner_subject="owner-1",
        idempotency_key="key-1",
        input_fingerprint="input-1",
        max_attempts=2,
        display_metadata={},
        allow_manual_retry=True,
        now=datetime.now(timezone.utc),
        )
    )

    listed = client.get("/api/v1/tasks")
    detail = client.get(f"/api/v1/tasks/{task.id}")
    hidden_client, _, _ = _client("owner-2")
    hidden = hidden_client.get(f"/api/v1/tasks/{task.id}")

    assert listed.status_code == 200
    assert listed.json()["tasks"][0]["id"] == str(task.id)
    assert "input_fingerprint" not in listed.text
    assert detail.status_code == 200
    assert hidden.status_code == 404
    assert hidden.json()["detail"]["code"] == "TASK_UNAVAILABLE"


def test_task_http_anonymous_and_command_validation_are_safe() -> None:
    client, _, _ = _client(None)
    assert client.get("/api/v1/tasks").status_code == 403
    invalid = client.post(f"/api/v1/tasks/{uuid4()}/cancel", json={"command_id": ""})
    assert invalid.status_code == 422


def test_task_http_pagination_errors_use_stable_code() -> None:
    client, _, _ = _client("owner-1")

    list_error = client.get("/api/v1/tasks?limit=201")
    event_error = client.get(f"/api/v1/tasks/{uuid4()}/events?after_sequence=0")

    assert list_error.status_code == 422
    assert list_error.json()["detail"]["code"] == "INVALID_TASK_PAGINATION"
    assert event_error.status_code == 422
    assert event_error.json()["detail"]["code"] == "INVALID_TASK_PAGINATION"


def test_task_http_cancel_replay_returns_current_projection_once() -> None:
    client, application, repository = _client("owner-1")
    task = application._repository.create_or_get_submission(  # noqa: SLF001
        Task.create(
            task_type="demo.execute",
            owner_subject="owner-1",
            idempotency_key="cancel-http-1",
            input_fingerprint="input-1",
            max_attempts=2,
            display_metadata={},
            allow_manual_retry=True,
            now=datetime.now(timezone.utc),
        )
    )

    first = client.post(f"/api/v1/tasks/{task.id}/cancel", json={"command_id": "cancel-1"})
    replay = client.post(f"/api/v1/tasks/{task.id}/cancel", json={"command_id": "cancel-1"})
    restored = repository.get(task.id)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert replay.json()["status"] == "cancelled"
    assert restored is not None
    assert len(restored.events) == 2


def test_task_http_retry_replay_returns_current_projection_once() -> None:
    client, application, repository = _client("owner-1")
    lifecycle = TaskLifecycleService(repository, clock=lambda: datetime.now(timezone.utc))
    submitted = lifecycle.submit(
        SubmitTaskCommand("owner-1", "demo.execute", "retry-http-1", "input-1", 2)
    )
    claimed = lifecycle.claim(
        ClaimTaskCommand(
            task_id=submitted.id,
            worker_id="worker-1",
            claim_id="claim-1",
            lease_token="lease-1",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    lifecycle.fail(
        FailTaskCommand(
            task_id=submitted.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            failure_category=FailureCategory.PERMANENT,
            failure_code="FAILED_FOR_HTTP_RETRY",
            result_fingerprint="failure-1",
        )
    )

    first = client.post(f"/api/v1/tasks/{submitted.id}/retry", json={"command_id": "retry-1"})
    replay = client.post(f"/api/v1/tasks/{submitted.id}/retry", json={"command_id": "retry-1"})
    restored = repository.get(submitted.id)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["status"] == "queued"
    assert replay.json()["status"] == "queued"
    assert restored is not None
    assert len(restored.events) == 4
