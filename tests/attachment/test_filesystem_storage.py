from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.modules.attachment import AttachmentAccessContext, AttachmentReadResult, AttachmentRef

OWNER = AttachmentAccessContext(subject="owner", conversation_id="conversation-1")
OTHER_SUBJECT = AttachmentAccessContext(subject="other", conversation_id="conversation-1")
OTHER_CONVERSATION = AttachmentAccessContext(subject="owner", conversation_id="conversation-2")


def _storage(tmp_path: Path, **kwargs: object) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf", "image/png"),
        **kwargs,
    )


def _stage(storage: FilesystemAttachmentStorage, content: bytes = b"content") -> AttachmentRef:
    return storage.stage_attachment(
        file_name="policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(content),
        context=OWNER,
    )


def test_stage_attachment_uses_random_id_and_reads_verified_content(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    content = b"dynamic attachment content"
    reference = storage.stage_attachment(
        file_name="../policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(content),
        context=OWNER,
    )

    assert len(reference.attachment_id) == 32
    assert reference.file_name == "policy.pdf"
    assert reference.size_bytes == len(content)
    assert reference.sha256
    result = storage.read(reference, context=OWNER)
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
            context=OWNER,
        )

    assert list(storage.attachment_root.iterdir()) == []


def test_stage_attachment_rejects_unsupported_media_type(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    with pytest.raises(ValueError, match="媒体类型"):
        storage.stage_attachment(
            file_name="policy.exe",
            media_type="application/x-msdownload",
            file_stream=BytesIO(b"content"),
            context=OWNER,
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
            context=OWNER,
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

    result = storage.read(forged, context=OWNER)

    assert result.status == "missing"
    assert result.error_code == "ATTACHMENT_NOT_FOUND"
    assert (outside / "secret.pdf").read_bytes() == b"secret"


def test_other_subject_cannot_read_or_delete_owner_attachment(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    reference = _stage(storage)

    result = storage.read(reference, context=OTHER_SUBJECT)

    assert result.status == "missing"
    assert result.attachment is None
    assert result.content is None
    assert storage.discard(reference.attachment_id, context=OTHER_SUBJECT) is False
    assert storage.read(reference, context=OWNER).content == b"content"


def test_same_subject_cannot_access_attachment_from_another_conversation(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    reference = _stage(storage)

    result = storage.read(reference.attachment_id, context=OTHER_CONVERSATION)

    assert result.status == "missing"
    assert result.attachment is None
    assert storage.consume(reference.attachment_id, context=OTHER_CONVERSATION).status == "missing"
    assert storage.read(reference, context=OWNER).content == b"content"


def test_anonymous_attachment_cannot_be_consumed_across_requests(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    anonymous = AttachmentAccessContext()
    reference = storage.stage_attachment(
        file_name="policy.pdf",
        media_type="application/pdf",
        file_stream=BytesIO(b"content"),
        context=anonymous,
    )

    result = storage.consume(reference.attachment_id, context=anonymous)

    assert result.status == "missing"
    assert result.error_code == "ATTACHMENT_NOT_FOUND"


def test_cleanup_expired_makes_reference_unavailable(tmp_path: Path) -> None:
    storage = _storage(tmp_path, retention_seconds=60)
    reference = _stage(storage)

    assert storage.cleanup_expired(now=datetime.now(UTC) + timedelta(seconds=61)) == 1
    result = storage.read(reference, context=OWNER)
    assert result.status == "expired"
    assert result.error_code == "ATTACHMENT_EXPIRED"
    assert result.content is None
    assert storage.consume(reference.attachment_id, context=OWNER).status == "expired"


def test_consume_is_one_time_and_removes_file(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    reference = _stage(storage)

    first = storage.consume(reference.attachment_id, context=OWNER)
    second = storage.consume(reference.attachment_id, context=OWNER)

    assert first.status == "available"
    assert first.content == b"content"
    assert second.status == "consumed"
    assert second.error_code == "ATTACHMENT_CONSUMED"
    assert not (storage.attachment_root / reference.attachment_id).exists()


def test_owner_can_discard_attachment_and_read_returns_missing(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    reference = _stage(storage)

    assert storage.discard(reference.attachment_id, context=OWNER) is True

    result = storage.read(reference, context=OWNER)
    assert result.status == "missing"
    assert result.error_code == "ATTACHMENT_NOT_FOUND"
