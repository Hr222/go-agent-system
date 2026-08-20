from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.interfaces.http.dependencies import get_attachment_storage
from app.main import create_app


class _FailingStorage:
    def stage_attachment(self, **kwargs: object) -> object:
        raise RuntimeError("/srv/private/attachments/secret")


def _client(tmp_path: Path, *, max_size_bytes: int = 50) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = lambda: FilesystemAttachmentStorage(
        tmp_path,
        max_size_bytes=max_size_bytes,
        allowed_media_types=("application/pdf", "image/png"),
    )
    return TestClient(application)


def test_upload_http_returns_dynamic_reference_and_safe_metadata(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.pdf", b"pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["attachment_id"]) == 32
    assert payload["file_name"] == "source.pdf"
    assert payload["media_type"] == "application/pdf"
    assert payload["size_bytes"] == len(b"pdf-content")
    assert len(payload["sha256"]) == 64
    assert payload["status"] == "available"
    assert "stored_path" not in payload
    assert "content" not in payload
    assert str(tmp_path) not in response.text


def test_upload_http_rest_alias_works_without_invoking_agents(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/attachments",
        files={"file": ("source.png", b"png-content", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["file_name"] == "source.png"


def test_upload_http_rejects_empty_file_and_leaves_no_attachment(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "INVALID_INPUT",
        "message": "附件上传内容无效。",
    }
    assert list((tmp_path / "attachments").iterdir()) == []


def test_upload_http_rejects_unsupported_type(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.exe", b"binary", "application/x-msdownload")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_INPUT"
    assert list((tmp_path / "attachments").iterdir()) == []


def test_upload_http_rejects_oversized_file_and_cleans_storage(tmp_path: Path) -> None:
    response = _client(tmp_path, max_size_bytes=3).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.pdf", b"1234", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_INPUT"
    assert list((tmp_path / "attachments").iterdir()) == []


def test_upload_http_does_not_leak_storage_error_or_invoke_agent() -> None:
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = _FailingStorage

    response = TestClient(application).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.pdf", b"content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "INVALID_INPUT",
        "message": "附件上传内容无效。",
    }
    assert "/srv/private" not in response.text
