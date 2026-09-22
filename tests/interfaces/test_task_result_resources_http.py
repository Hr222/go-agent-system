from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_task_result_resource_application,
)
from app.interfaces.http.routes.tasks import router
from app.interfaces.http.security import get_request_principal
from app.platform.security import RequestPrincipal
from app.platform.task.application import TaskResultResourcesQuery, TaskResultResourcesView
from app.platform.task.errors import TaskAccessDeniedError, TaskResultResourceUnavailableError
from app.platform.task.ports import TaskResultResource


class StubResultResourcesApplication:
    def __init__(self, result: TaskResultResourcesView | Exception) -> None:
        self.result = result
        self.queries: list[TaskResultResourcesQuery] = []

    def list_owned(self, query: TaskResultResourcesQuery) -> TaskResultResourcesView:
        self.queries.append(query)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _client(
    principal: RequestPrincipal,
    application: StubResultResourcesApplication,
) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/tasks")
    test_app.dependency_overrides[get_task_result_resource_application] = lambda: application
    test_app.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(test_app)


def test_task_resources_http_returns_safe_metadata_and_server_download_url() -> None:
    task_id = uuid4()
    conversation_id = str(uuid4())
    resource = TaskResultResource(
        resource_id="resource-1",
        file_name="result.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=12,
        sha256="a" * 64,
    )
    application = StubResultResourcesApplication(
        TaskResultResourcesView(task_id, conversation_id, (resource,))
    )
    client = _client(RequestPrincipal("owner-1", authenticated=True), application)

    response = client.get(f"/api/v1/tasks/{task_id}/resources")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": str(task_id),
        "resources": [
            {
                "resource_id": "resource-1",
                "file_name": "result.docx",
                "media_type": resource.media_type,
                "size_bytes": 12,
                "sha256": "a" * 64,
                "download_url": f"/api/v1/attachments/resource-1/download?conversation_id={conversation_id}",
            }
        ],
    }
    assert application.queries[0].task_id == task_id
    assert application.queries[0].principal.subject == "owner-1"


def test_task_resources_http_maps_auth_and_unavailable_states() -> None:
    task_id = uuid4()
    unavailable = StubResultResourcesApplication(
        TaskResultResourceUnavailableError("hidden")
    )
    unavailable_client = _client(
        RequestPrincipal("owner-1", authenticated=True), unavailable
    )
    anonymous = StubResultResourcesApplication(
        TaskAccessDeniedError("should not be called")
    )
    anonymous_client = _client(RequestPrincipal(None, authenticated=False), anonymous)

    unavailable_response = unavailable_client.get(f"/api/v1/tasks/{task_id}/resources")
    anonymous_response = anonymous_client.get(f"/api/v1/tasks/{task_id}/resources")

    assert unavailable_response.status_code == 404
    assert unavailable_response.json()["detail"]["code"] == "TASK_RESOURCES_UNAVAILABLE"
    assert anonymous_response.status_code == 403
    assert anonymous_response.json()["detail"]["code"] == "TASK_ACCESS_DENIED"
