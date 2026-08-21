from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.interfaces.http.dependencies import get_attachment_storage
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.modules.attachment import AttachmentAccessContext
from app.modules.security import RequestPrincipal


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
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="test-owner",
        authenticated=True,
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


def test_upload_http_binds_the_server_resolved_principal(tmp_path: Path) -> None:
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf",),
    )
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = lambda: storage
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="static-owner",
        authenticated=True,
    )

    response = TestClient(application).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.pdf", b"pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    attachment_id = response.json()["attachment_id"]
    assert storage.read(
        attachment_id,
        context=AttachmentAccessContext(subject="static-owner"),
    ).content == b"pdf-content"
    assert storage.read(
        attachment_id,
        context=AttachmentAccessContext(subject="other-owner"),
    ).status == "missing"


def test_upload_http_rejects_anonymous_principal_without_writing_attachment(
    tmp_path: Path,
) -> None:
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf",),
    )
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = lambda: storage
    application.dependency_overrides[get_request_principal] = RequestPrincipal.anonymous

    response = TestClient(application).post(
        "/api/v1/attachments/upload",
        files={"file": ("source.pdf", b"pdf-content", "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "code": "ATTACHMENT_PRINCIPAL_REQUIRED",
            "message": "上传附件需要可信请求主体。",
        }
    }
    assert list(storage.attachment_root.iterdir()) == []


def test_upload_http_binds_optional_conversation_context(tmp_path: Path) -> None:
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf",),
    )
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = lambda: storage
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="static-owner",
        authenticated=True,
    )
    conversation_id = UUID("00000000-0000-0000-0000-000000000001")

    response = TestClient(application).post(
        "/api/v1/attachments/upload",
        data={"conversation_id": str(conversation_id)},
        files={"file": ("source.pdf", b"pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    attachment_id = response.json()["attachment_id"]
    assert storage.read(
        attachment_id,
        context=AttachmentAccessContext(
            subject="static-owner",
            conversation_id=str(conversation_id),
        ),
    ).content == b"pdf-content"
    assert storage.read(
        attachment_id,
        context=AttachmentAccessContext(
            subject="static-owner",
            conversation_id="00000000-0000-0000-0000-000000000002",
        ),
    ).status == "missing"


def test_download_http_returns_attachment_only_for_matching_subject_and_conversation(
    tmp_path: Path,
) -> None:
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf",),
    )
    conversation_id = UUID("00000000-0000-0000-0000-000000000001")
    attachment = storage.stage_attachment(
        file_name="source.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(b"pdf-content"),
        context=AttachmentAccessContext(
            subject="static-owner",
            conversation_id=str(conversation_id),
        ),
    )
    application = create_app()
    application.dependency_overrides[get_attachment_storage] = lambda: storage
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="static-owner",
        authenticated=True,
    )
    client = TestClient(application)
    download_url = (
        f"/api/v1/attachments/{attachment.attachment_id}/download"
        f"?conversation_id={conversation_id}"
    )

    response = client.get(download_url)

    assert response.status_code == 200
    assert response.content == b"pdf-content"
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''source.pdf"
    assert response.headers["cache-control"] == "private, no-store"

    wrong_conversation = client.get(
        f"/api/v1/attachments/{attachment.attachment_id}/download"
        "?conversation_id=00000000-0000-0000-0000-000000000002"
    )
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="other-owner",
        authenticated=True,
    )
    wrong_subject = client.get(download_url)
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="static-owner",
        authenticated=True,
    )
    missing = client.get(
        "/api/v1/attachments/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download"
        f"?conversation_id={conversation_id}"
    )

    unavailable_payload = {
        "detail": {"code": "ATTACHMENT_UNAVAILABLE", "message": "资源不可用。"}
    }
    for unavailable in (wrong_conversation, wrong_subject, missing):
        assert unavailable.status_code == 404
        assert unavailable.json() == unavailable_payload
        assert unavailable.content != b"pdf-content"


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
    application.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        subject="test-owner",
        authenticated=True,
    )

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
