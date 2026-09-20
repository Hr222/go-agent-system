from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.business.agents.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderGenerateSkeletonResult,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.business.agents.tender.ports.task_port import (
    FilesystemTenderTaskResultStore,
    TenderResultResourceStoreError,
)
from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_CONVERSATION_ID = "00000000-0000-0000-0000-000000000001"


def _result(*artifacts: tuple[str, bytes]) -> TenderGenerateSkeletonResult:
    return TenderGenerateSkeletonResult(
        analysis=TenderAnalysis(
            status="completed",
            package_type="single_volume",
            summary="合成分析",
            outputs=[
                TenderOutputPlan(
                    name="投标文件",
                    slug="bid",
                    document_label="投标文件",
                )
            ],
            evidence=[TenderSourceEvidence(evidence_id="e1", location="p1", quote="合成证据")],
        ),
        artifacts=tuple(
            GeneratedTenderArtifact(file_name, _DOCX_MEDIA_TYPE, content)
            for file_name, content in artifacts
        ),
        model="test-model",
        prompt_version="test-prompt",
    )


def _storage(workspace: Path) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(
        workspace,
        allowed_media_types=(_DOCX_MEDIA_TYPE,),
        retention_seconds=60,
    )


def test_resource_store_stages_idempotent_conversation_bound_files(tmp_path: Path) -> None:
    attachment_workspace = tmp_path / "attachments-workspace"
    result_workspace = tmp_path / "result-workspace"
    task_id = uuid4()
    result = _result(("technical.docx", b"technical"), ("business.docx", b"business"))
    store = FilesystemTenderTaskResultStore(
        result_workspace,
        attachment_storage=_storage(attachment_workspace),
    )

    first = store.save(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
        result=result,
    )
    second = store.save(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
        result=result,
    )
    resources = store.list_resources(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
    )

    assert first == second == f"tender-result:{task_id}"
    assert resources is not None
    assert [resource.file_name for resource in resources] == [
        "technical.docx",
        "business.docx",
    ]
    payload = json.loads((result_workspace / f"{task_id}.json").read_text(encoding="utf-8"))
    assert "content_base64" not in json.dumps(payload)
    assert payload["resources"][0]["resource_id"] == resources[0].resource_id
    assert store.list_resources(
        task_id=task_id,
        owner_subject="other-owner",
        conversation_id=_CONVERSATION_ID,
    ) is None
    assert store.list_resources(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id="00000000-0000-0000-0000-000000000002",
    ) is None

    restarted = FilesystemTenderTaskResultStore(
        result_workspace,
        attachment_storage=_storage(attachment_workspace),
    )
    restored = restarted.list_resources(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
    )
    assert restored == resources


class _SecondWriteFailsStorage(FilesystemAttachmentStorage):
    def __init__(self, workspace_root: Path) -> None:
        super().__init__(workspace_root, allowed_media_types=(_DOCX_MEDIA_TYPE,))
        self._stage_count = 0

    def stage_attachment(self, **kwargs):  # noqa: ANN003 - preserve the storage Port signature
        self._stage_count += 1
        if self._stage_count == 2:
            raise OSError("simulated result write failure")
        return super().stage_attachment(**kwargs)


def test_resource_store_cleans_partial_attachments_when_later_artifact_fails(
    tmp_path: Path,
) -> None:
    storage = _SecondWriteFailsStorage(tmp_path / "attachments-workspace")
    result_workspace = tmp_path / "result-workspace"
    store = FilesystemTenderTaskResultStore(result_workspace, attachment_storage=storage)
    task_id = uuid4()

    with pytest.raises(TenderResultResourceStoreError):
        store.save(
            task_id=task_id,
            owner_subject="owner-1",
            conversation_id=_CONVERSATION_ID,
            result=_result(("first.docx", b"first"), ("second.docx", b"second")),
        )

    assert list(storage.attachment_root.iterdir()) == []
    assert not (result_workspace / f"{task_id}.json").exists()
    assert not (result_workspace / "resources" / f"{task_id}.json").exists()


def test_mcp_style_result_without_conversation_preserves_internal_storage_only(
    tmp_path: Path,
) -> None:
    store = FilesystemTenderTaskResultStore(
        tmp_path / "result-workspace",
        attachment_storage=_storage(tmp_path / "attachments-workspace"),
    )
    task_id = uuid4()
    store.save(
        task_id=task_id,
        owner_subject="owner-1",
        result=_result(("mcp.docx", b"mcp-result")),
    )

    payload = json.loads(
        (tmp_path / "result-workspace" / f"{task_id}.json").read_text(encoding="utf-8")
    )
    assert "resources" not in payload
    assert payload["artifacts"][0]["content_base64"]
    assert list((tmp_path / "attachments-workspace" / "attachments").iterdir()) == []


def test_resource_store_returns_none_after_attachment_expiry(tmp_path: Path) -> None:
    attachment_workspace = tmp_path / "attachments-workspace"
    storage = FilesystemAttachmentStorage(
        attachment_workspace,
        allowed_media_types=(_DOCX_MEDIA_TYPE,),
        retention_seconds=1,
    )
    store = FilesystemTenderTaskResultStore(
        tmp_path / "result-workspace",
        attachment_storage=storage,
    )
    task_id = uuid4()
    store.save(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
        result=_result(("expired.docx", b"expired")),
    )
    storage.cleanup_expired(now=datetime.now(UTC) + timedelta(seconds=2))

    assert store.list_resources(
        task_id=task_id,
        owner_subject="owner-1",
        conversation_id=_CONVERSATION_ID,
    ) is None
