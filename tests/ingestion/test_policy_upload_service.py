import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.infrastructure.filesystem.upload_service import PolicyUploadService
from app.interfaces.http.schemas.policy_upload import PolicyUploadIngestRequest


def _upload(file_name: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=file_name)


def test_stage_upload_limits_size_and_removes_partial_directory(tmp_path: Path) -> None:
    service = PolicyUploadService(tmp_path, max_size_bytes=3)
    upload = _upload("policy.pdf", b"1234")

    with pytest.raises(ValueError, match="不能超过"):
        service.stage_upload(file_name=upload.filename, file_stream=upload.file)

    assert list(service.upload_root.iterdir()) == []


def test_resolve_upload_rejects_non_generated_ids(tmp_path: Path) -> None:
    service = PolicyUploadService(tmp_path)
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (outside_directory / "policy.pdf").write_bytes(b"outside")

    with pytest.raises(ValueError, match="格式无效"):
        service.resolve_upload("../outside")
    with pytest.raises(ValueError, match="格式无效"):
        service.resolve_upload(str(outside_directory.resolve()))


def test_discard_upload_removes_staged_file(tmp_path: Path) -> None:
    service = PolicyUploadService(tmp_path)
    upload = _upload("policy.pdf", b"content")

    staged = service.stage_upload(file_name=upload.filename, file_stream=upload.file)
    assert Path(staged.stored_path).read_bytes() == b"content"

    service.discard_upload(staged.upload_id)

    assert not Path(staged.stored_path).exists()
    assert not (service.upload_root / staged.upload_id).exists()


def test_promote_upload_keeps_the_original_file_for_later_preview(tmp_path: Path) -> None:
    service = PolicyUploadService(tmp_path)
    upload = _upload("certificate.jpg", b"image-content")

    staged = service.stage_upload(file_name=upload.filename, file_stream=upload.file)
    promoted_path = Path(service.promote_upload(staged.upload_id))

    assert promoted_path.read_bytes() == b"image-content"
    assert promoted_path.parent == service.document_root / staged.upload_id
    assert not (service.upload_root / staged.upload_id).exists()


def test_cleanup_expired_removes_old_staged_files(tmp_path: Path) -> None:
    service = PolicyUploadService(tmp_path, retention_seconds=60)
    upload = _upload("policy.pdf", b"content")
    staged = service.stage_upload(file_name=upload.filename, file_stream=upload.file)
    old_timestamp = (datetime.now(UTC) - timedelta(seconds=120)).timestamp()
    os.utime(service.upload_root / staged.upload_id, (old_timestamp, old_timestamp))

    removed_count = service.cleanup_expired(now=datetime.now(UTC))

    assert removed_count == 1
    assert not (service.upload_root / staged.upload_id).exists()


def test_upload_request_rejects_invalid_upload_id() -> None:
    with pytest.raises(ValidationError):
        PolicyUploadIngestRequest(upload_id="../outside")
