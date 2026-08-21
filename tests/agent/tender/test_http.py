from __future__ import annotations

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_stateless_application_container
from app.main import create_app


def test_legacy_tender_http_route_is_retired_without_resolving_container() -> None:
    application = create_app()
    dependency_calls = 0

    def unexpected_container() -> object:
        nonlocal dependency_calls
        dependency_calls += 1
        raise AssertionError("retired route must not resolve the Tender container")

    application.dependency_overrides[get_stateless_application_container] = unexpected_container

    response = TestClient(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"source", "application/octet-stream")},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert dependency_calls == 0
