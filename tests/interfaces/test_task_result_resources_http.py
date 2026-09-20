from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_owned_task_application,
    get_task_result_resource_application,
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
    TaskResultResource,
    TaskResultResourceApplication,
)
from app.platform.task.application.executor_contracts import (
    ClaimTaskCommand,
    CompleteTaskCommand,
)
from tests.task.in_memory_repository import InMemoryTaskRepository

_CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000001")


class _ResourceReader:
    def __init__(self) -> None:
        self.resources = (
            TaskResultResource(
                resource_id="a" * 32,
                file_name="bid.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=12,
                sha256="b" * 64,
            ),
        )

    def list_resources(self, *, task_id, owner_subject, conversation_id):  # noqa: ANN001
        del task_id, owner_subject, conversation_id
        return self.resources


def _client(subject: str | None):
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    owned_application = OwnedTaskApplication(
        repository,
        CancellationCoordinator(lifecycle),
        ManualRetryCoordinator(lifecycle),
    )
    result_application = TaskResultResourceApplication(repository, _ResourceReader())
    principal = RequestPrincipal(subject=subject, authenticated=subject is not None)
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/tasks")
    test_app.dependency_overrides[get_owned_task_application] = lambda: owned_application
    test_app.dependency_overrides[get_task_result_resource_application] = lambda: result_application
    test_app.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(test_app), lifecycle


def _complete_tender_task(lifecycle: TaskLifecycleService):  # noqa: ANN201
    task = lifecycle.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="tender.generate_bid_skeleton",
            idempotency_key="task-http-resources",
            input_fingerprint="input-fingerprint",
            max_attempts=2,
            display_metadata={"conversation_id": str(_CONVERSATION_ID)},
        )
    )
    claimed = lifecycle.claim(
        ClaimTaskCommand(
            task_id=task.id,
            worker_id="worker-1",
            claim_id="claim-1",
            lease_token="lease-1",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    lifecycle.complete(
        CompleteTaskCommand(
            task_id=task.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="result-fingerprint",
            result_summary="Tender 投标骨架已生成。",
        )
    )
    return task


def test_task_resource_http_returns_safe_download_metadata() -> None:
    client, lifecycle = _client("owner-1")
    task = _complete_tender_task(lifecycle)

    response = client.get(
        f"/api/v1/tasks/{task.id}/resources?conversation_id={_CONVERSATION_ID}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == str(task.id)
    assert payload["resources"] == [
        {
            "resource_id": "a" * 32,
            "file_name": "bid.docx",
            "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 12,
            "sha256": "b" * 64,
            "download_url": (
                "/api/v1/attachments/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download"
                f"?conversation_id={_CONVERSATION_ID}"
            ),
        }
    ]
    assert "lease" not in response.text
    assert "input_fingerprint" not in response.text
    assert "content_base64" not in response.text


def test_task_resource_http_hides_wrong_conversation_and_rejects_anonymous() -> None:
    client, lifecycle = _client("owner-1")
    task = _complete_tender_task(lifecycle)

    wrong_conversation = client.get(
        f"/api/v1/tasks/{task.id}/resources"
        "?conversation_id=00000000-0000-0000-0000-000000000002"
    )
    anonymous_client, _ = _client(None)
    anonymous = anonymous_client.get(
        f"/api/v1/tasks/{task.id}/resources?conversation_id={_CONVERSATION_ID}"
    )

    assert wrong_conversation.status_code == 404
    assert wrong_conversation.json() == {
        "detail": {"code": "TASK_RESOURCES_UNAVAILABLE", "message": "任务结果资源不可用。"}
    }
    assert anonymous.status_code == 403
