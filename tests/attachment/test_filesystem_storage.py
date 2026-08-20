from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.modules.attachment import AttachmentReadResult, AttachmentRef


def _storage(tmp_path: Path, **kwargs: object) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf", "image/png"),
        **kwargs,
    )


def test_stage_attachment_uses_random_id_and_reads_verified_content(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    content = b"dynamic attachment content"

    reference = storage.stage_attachment(
        file_name="../policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(content),
    )

    assert len(reference.attachment_id) == 32
    assert reference.file_name == "policy.pdf"
    assert reference.size_bytes == len(content)
    assert reference.sha256
    result = storage.read(reference)
    assert result == AttachmentReadResult(
        status="available", attachment=reference, content=content
    )
    assert list((storage.attachment_root / reference.attachment_id).glob("*.part")) == []


def test_stage_attachment_rejects_size_limit_without_partial_file(tmp_path: Path) -> None:
    storage = _storage(tmp_path, max_size_bytes=3)

    with pytest.raises(ValueError, match="不能超过"):
        storage.stage_attachment(
            file_name="policy.pdf",
            media_type="application/pdf",
            file_stream=BytesIO(b"1234"),
        )

    assert list(storage.attachment_root.iterdir()) == []


def test_stage_attachment_rejects_unsupported_media_type(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    with pytest.raises(ValueError, match="媒体类型"):
        storage.stage_attachment(
            file_name="policy.exe",
            media_type="application/x-msdownload",
            file_stream=BytesIO(b"content"),
        )

    assert list(storage.attachment_root.iterdir()) == []


class _FailingStream:
    def __init__(self) -> None:
        self._chunks = iter((b"partial", RuntimeError("read failed")))

    def seek(self, offset: int) -> None:
        assert offset == 0

    def read(self, size: int) -> bytes:
        chunk = next(self._chunks)
        if isinstance(chunk, Exception):
            raise chunk
        return chunk


def test_partial_stream_failure_removes_staging_directory(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    with pytest.raises(RuntimeError, match="read failed"):
        storage.stage_attachment(
            file_name="policy.pdf",
            media_type="application/pdf",
            file_stream=_FailingStream(),  # type: ignore[arg-type]
        )

    assert list(storage.attachment_root.iterdir()) == []


def test_read_rejects_non_generated_id_without_accessing_outside_root(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.pdf").write_bytes(b"secret")
    forged = object.__new__(AttachmentRef)
    object.__setattr__(forged, "attachment_id", "../outside")
    object.__setattr__(forged, "file_name", "secret.pdf")
    object.__setattr__(forged, "media_type", "application/pdf")
    object.__setattr__(forged, "size_bytes", 6)
    object.__setattr__(forged, "sha256", "a" * 64)
    object.__setattr__(forged, "status", "available")

    result = storage.read(forged)

    assert result.status == "missing"
    assert result.error_code == "ATTACHMENT_NOT_FOUND"
    assert (outside / "secret.pdf").read_bytes() == b"secret"


def test_cleanup_expired_makes_reference_unavailable(tmp_path: Path) -> None:
    storage = _storage(tmp_path, retention_seconds=60)
    reference = storage.stage_attachment(
        file_name="policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(b"content"),
    )
    old_timestamp = (datetime.now(UTC) - timedelta(seconds=120)).timestamp()
    os.utime(storage.attachment_root / reference.attachment_id, (old_timestamp, old_timestamp))

    assert storage.cleanup_expired(now=datetime.now(UTC)) == 1
    result = storage.read(reference)
    assert result.status == "expired"
    assert result.error_code == "ATTACHMENT_EXPIRED"
    assert result.content is None


def test_discard_removes_attachment_and_read_returns_missing(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    reference = storage.stage_attachment(
        file_name="policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(b"content"),
    )

    storage.discard(reference.attachment_id)

    result = storage.read(reference)
    assert result.status == "missing"
    assert result.error_code == "ATTACHMENT_NOT_FOUND"
