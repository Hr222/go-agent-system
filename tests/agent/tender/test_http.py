from __future__ import annotations

import base64
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_stateless_application_container
from app.main import create_app
from app.modules.agent.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderGenerateSkeletonResult,
)
from app.modules.agent.tender.errors import (
    TenderAnalysisError,
    TenderDocumentParseError,
    TenderRenderError,
)
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


@dataclass
class FakeTenderApplication:
    result: TenderGenerateSkeletonResult | None = None
    error: Exception | None = None
    calls: int = 0

    def execute(self, command: object) -> TenderGenerateSkeletonResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class FakeContainer:
    application: FakeTenderApplication

    def tender_application(self) -> FakeTenderApplication:
        return self.application


def _result() -> TenderGenerateSkeletonResult:
    return TenderGenerateSkeletonResult(
        analysis=TenderAnalysis(
            status="completed",
            package_type="single_volume",
            summary="http smoke",
            outputs=[],
        ),
        artifacts=(
            GeneratedTenderArtifact(
                file_name="skeleton.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=b"docx-content",
            ),
        ),
        model="fake-model",
        prompt_version="tender-skeleton-v1",
    )


def _client(application: FakeTenderApplication) -> TestClient:
    fastapi_app = create_app()
    fastapi_app.dependency_overrides[get_stateless_application_container] = (
        lambda: FakeContainer(application)
    )
    return TestClient(fastapi_app)


def test_tender_http_returns_analysis_and_embedded_artifact() -> None:
    application = FakeTenderApplication(result=_result())

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={
            "file": (
                "source.docx",
                b"source",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"user_focus": "关注文件分线"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis"]["summary"] == "http smoke"
    assert payload["artifacts"][0]["file_name"] == "skeleton.docx"
    assert base64.b64decode(payload["artifacts"][0]["content_base64"]) == b"docx-content"
    assert application.calls == 1


def test_tender_http_rejects_invalid_file_before_application() -> None:
    application = FakeTenderApplication(result=_result())

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.pdf", b"source", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "INVALID_INPUT",
        "message": "Tender 只接收 DOCX 招标文件。",
    }
    assert application.calls == 0


def test_tender_http_maps_model_configuration_failure_without_provider_detail() -> None:
    application = FakeTenderApplication(error=ServiceNotConfiguredError("secret-value"))

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"source", "application/octet-stream")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "SERVICE_NOT_CONFIGURED",
        "message": "Tender Agent 模型服务尚未配置。",
    }
    assert "secret-value" not in response.text


def test_tender_http_rejects_empty_file_before_application() -> None:
    application = FakeTenderApplication(result=_result())

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_INPUT"
    assert application.calls == 0


def test_tender_http_rejects_size_limit_before_application(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.interfaces.http.routes import tender

    monkeypatch.setattr(tender.settings, "tender_upload_max_size_bytes", 3)
    application = FakeTenderApplication(result=_result())

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"1234", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_INPUT"
    assert application.calls == 0


def test_tender_http_rejects_hard_size_limit_before_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.interfaces.http.routes import tender

    monkeypatch.setattr(tender.settings, "tender_upload_max_size_bytes", 100)
    monkeypatch.setattr(tender.settings, "tender_hard_max_size_bytes", 3)
    application = FakeTenderApplication(result=_result())

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"1234", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "INVALID_INPUT",
        "message": "招标文件超过服务端硬性大小限制。",
    }
    assert application.calls == 0


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (TenderDocumentParseError("provider path"), 422, "DOCUMENT_PARSE_FAILED"),
        (UpstreamServiceError("provider raw response"), 502, "UPSTREAM_FAILED"),
        (TenderAnalysisError("schema details"), 422, "ANALYSIS_FAILED"),
        (TenderRenderError("local temp path"), 500, "RENDER_FAILED"),
    ],
)
def test_tender_http_maps_application_failures(
    error: Exception,
    status_code: int,
    error_code: str,
) -> None:
    application = FakeTenderApplication(error=error)

    response = _client(application).post(
        "/api/v1/agents/tender/skeleton",
        files={"file": ("source.docx", b"source", "application/octet-stream")},
    )

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == error_code
    assert "provider" not in response.text
    assert "local temp path" not in response.text
