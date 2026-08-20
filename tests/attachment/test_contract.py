from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.infrastructure.filesystem.upload_service import PolicyUploadService
from app.modules.attachment import (
    AttachmentReadPort,
    AttachmentReadResult,
    AttachmentRef,
)
from app.modules.ingestion.ports import StagedUpload, UploadStoragePort


_SHA256 = "a" * 64


class FakeAttachmentReader:
    def __init__(self, result: AttachmentReadResult) -> None:
        self.result = result
        self.requested: list[str] = []

    def read(self, attachment: AttachmentRef) -> AttachmentReadResult:
        self.requested.append(attachment.attachment_id)
        return self.result


def _ref() -> AttachmentRef:
    return AttachmentRef.issue(
        file_name="招标文件.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=42,
        sha256=_SHA256,
    )


def test_attachment_ref_issues_opaque_safe_metadata_only() -> None:
    reference = _ref()
    public = reference.public_dict()

    assert len(reference.attachment_id) == 32
    assert reference.status == "available"
    assert json.loads(json.dumps(public, ensure_ascii=False)) == public
    assert set(public) == {
        "attachment_id",
        "file_name",
        "media_type",
        "size_bytes",
        "sha256",
        "status",
    }
    assert "stored_path" not in public
    assert "content" not in public


@pytest.mark.parametrize(
    "kwargs",
    (
        {"attachment_id": "../outside"},
        {"attachment_id": "a" * 64},
        {"file_name": ""},
        {"media_type": ""},
        {"size_bytes": -1},
        {"sha256": "not-a-digest"},
    ),
)
def test_attachment_ref_rejects_unsafe_or_invalid_metadata(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "attachment_id": "b" * 32,
        "file_name": "source.docx",
        "media_type": "application/octet-stream",
        "size_bytes": 1,
        "sha256": _SHA256,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        AttachmentRef(**values)  # type: ignore[arg-type]


def test_attachment_read_port_returns_content_without_exposing_storage_details() -> None:
    reference = _ref()
    reader = FakeAttachmentReader(
        AttachmentReadResult(status="available", attachment=reference, content=b"docx")
    )
    port: AttachmentReadPort = reader

    result = port.read(reference)

    assert result.status == "available"
    assert result.content == b"docx"
    assert result.attachment == reference
    assert result.attachment is not None
    assert "stored_path" not in result.attachment.public_dict()
    assert reader.requested == [reference.attachment_id]


@pytest.mark.parametrize(
    ("status", "error_code"),
    (
        ("expired", "ATTACHMENT_EXPIRED"),
        ("missing", "ATTACHMENT_NOT_FOUND"),
        ("consumed", "ATTACHMENT_CONSUMED"),
    ),
)
def test_unavailable_attachment_references_never_return_content(
    status: str,
    error_code: str,
) -> None:
    result = AttachmentReadResult.unavailable(
        status=status,  # type: ignore[arg-type]
        error_code=error_code,  # type: ignore[arg-type]
    )

    assert result.content is None
    assert result.attachment is None
    assert result.error_code == error_code


def test_existing_policy_upload_contract_remains_path_based(tmp_path: Path) -> None:
    upload_port: UploadStoragePort = PolicyUploadService(tmp_path)
    staged = upload_port.stage_upload(
        file_name="policy.pdf",
        file_stream=BytesIO(b"policy"),
    )

    assert isinstance(staged, StagedUpload)
    assert staged.upload_id
    assert staged.file_name == "policy.pdf"
    assert staged.stored_path
    assert staged.size_bytes == 6
    assert Path(staged.stored_path).read_bytes() == b"policy"
    upload_port.discard_upload(staged.upload_id)


def test_upload_file_fixture_matches_existing_policy_upload_adapter() -> None:
    upload = UploadFile(file=BytesIO(b"policy"), filename="policy.pdf")
    assert upload.filename == "policy.pdf"
