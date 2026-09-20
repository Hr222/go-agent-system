from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.business.agents.tender.application.task_execution import (
    TenderTaskExecutor,
    TenderTaskInputSnapshotProvider,
)
from app.business.agents.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderGenerateSkeletonResult,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.business.agents.tender.ports.task_port import (
    AttachmentTenderTaskInputReader,
    InMemoryTenderTaskResultStore,
)
from app.platform.attachment.contracts import (
    AttachmentAccessContext,
    AttachmentReadResult,
    AttachmentRef,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.attachment import ResolvedAttachment
from app.platform.interaction.ports.agent_task_bridge import AgentTaskProfile
from app.platform.task.application.executor_contracts import AttemptLease
from app.platform.task.domain import FailureCategory
from app.platform.task.ports.worker import (
    TaskExecutionCancellation,
    TaskExecutionContext,
    TaskExecutionFailure,
    TaskExecutionSuccess,
)
from app.shared.exceptions import UpstreamServiceError


class FakeAttachmentStorage:
    def __init__(
        self,
        content: bytes,
        reference: AttachmentRef,
        *,
        allowed_subject: str = "owner-1",
    ) -> None:
        self.content = content
        self.reference = reference
        self.allowed_subject = allowed_subject
        self.contexts: list[AttachmentAccessContext] = []

    def read(self, attachment, *, context):  # noqa: ANN001
        self.contexts.append(context)
        if attachment != self.reference.attachment_id or context.subject != self.allowed_subject:
            return AttachmentReadResult.unavailable(
                status="missing", error_code="ATTACHMENT_NOT_FOUND"
            )
        return AttachmentReadResult(
            status="available", attachment=self.reference, content=self.content
        )


class FakeTenderApplication:
    def __init__(self, result=None, error: Exception | None = None) -> None:  # noqa: ANN001
        self.result = result
        self.error = error
        self.commands = []

    def execute(self, command):  # noqa: ANN001
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.result


def _reference(content: bytes = b"docx") -> AttachmentRef:
    import hashlib

    return AttachmentRef.issue(
        file_name="tender.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _result() -> TenderGenerateSkeletonResult:
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
        artifacts=(
            GeneratedTenderArtifact(
                "bid.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                b"PK",
            ),
        ),
        model="test-model",
        prompt_version="test-prompt",
    )


def _context(
    reference: AttachmentRef,
    *,
    owner: str = "owner-1",
    cancel=None,  # noqa: ANN001
) -> TaskExecutionContext:
    task_id = uuid4()
    now = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    lease = AttemptLease(
        attempt_id=uuid4(),
        worker_id="worker-1",
        lease_token="lease-token",
        lease_expires_at=now + timedelta(minutes=5),
        renewal_sequence=0,
    )
    return TaskExecutionContext(
        task_id=task_id,
        task_type="tender.generate_bid_skeleton",
        owner_subject=owner,
        display_metadata={
            "snapshot_reference": reference.attachment_id,
            "file_name": reference.file_name,
            "media_type": reference.media_type,
            "sha256": reference.sha256,
            "user_focus": "重点关注格式",
        },
        lease=lease,
        renew_lease=lambda: lease,
        is_cancel_requested=cancel,
    )


def test_snapshot_provider_requires_server_resolved_attachment_and_is_deterministic() -> None:
    reference = _reference()
    call = StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        conversation_id="conversation-1",
        inputs={
            "source_document": ResolvedAttachment(reference=reference, content=b"docx"),
            "user_focus": "重点关注格式",
        },
    )
    profile = AgentTaskProfile(
        capability_code=call.capability_code,
        task_type="tender.generate_bid_skeleton",
        max_attempts=2,
        display_metadata_fields=(
            "snapshot_reference",
            "file_name",
            "media_type",
            "sha256",
            "user_focus",
            "conversation_id",
        ),
    )

    first = TenderTaskInputSnapshotProvider().snapshot(call, profile)
    second = TenderTaskInputSnapshotProvider().snapshot(call, profile)

    assert first.input_fingerprint == second.input_fingerprint
    assert first.snapshot_reference == reference.attachment_id
    assert first.display_metadata["sha256"] == reference.sha256


def test_snapshot_provider_rejects_raw_document_input() -> None:
    call = StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        inputs={"source_document": "a" * 32},
    )

    try:
        TenderTaskInputSnapshotProvider().snapshot(
            call,
            AgentTaskProfile(
                capability_code=call.capability_code,
                task_type="tender.generate_bid_skeleton",
                max_attempts=2,
            ),
        )
    except ValueError as exc:
        assert "已解析附件" in str(exc)
    else:
        raise AssertionError("原始附件 ID 必须被异步快照拒绝")


def test_executor_reads_snapshot_as_owner_and_saves_safe_result() -> None:
    content = b"docx"
    reference = _reference(content)
    storage = FakeAttachmentStorage(content, reference)
    application = FakeTenderApplication(_result())
    result_store = InMemoryTenderTaskResultStore()
    executor = TenderTaskExecutor(
        application=application,
        input_reader=AttachmentTenderTaskInputReader(storage),
        result_store=result_store,
    )

    context = _context(reference)
    outcome = executor.execute(context)

    assert isinstance(outcome, TaskExecutionSuccess)
    assert len(result_store.results) == 1
    assert storage.contexts[0].subject == "owner-1"
    assert application.commands[0].content == content
    assert "docx" not in outcome.result_summary


def test_executor_maps_upstream_failure_to_retryable_safe_result() -> None:
    content = b"docx"
    reference = _reference(content)
    executor = TenderTaskExecutor(
        application=FakeTenderApplication(error=UpstreamServiceError("secret response")),
        input_reader=AttachmentTenderTaskInputReader(FakeAttachmentStorage(content, reference)),
        result_store=InMemoryTenderTaskResultStore(),
        clock=lambda: datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
    )

    outcome = executor.execute(_context(reference))

    assert isinstance(outcome, TaskExecutionFailure)
    assert outcome.failure_category is FailureCategory.TRANSIENT
    assert outcome.failure_code == "TENDER_UPSTREAM_FAILED"
    assert outcome.retry_at is not None


def test_executor_rejects_snapshot_read_for_different_owner() -> None:
    content = b"docx"
    reference = _reference(content)
    executor = TenderTaskExecutor(
        application=FakeTenderApplication(_result()),
        input_reader=AttachmentTenderTaskInputReader(
            FakeAttachmentStorage(content, reference, allowed_subject="owner-1")
        ),
        result_store=InMemoryTenderTaskResultStore(),
    )

    outcome = executor.execute(_context(reference, owner="other-owner"))

    assert isinstance(outcome, TaskExecutionFailure)
    assert outcome.failure_code == "TENDER_INPUT_SNAPSHOT_UNAVAILABLE"


def test_result_store_is_idempotent_by_task_id(tmp_path) -> None:  # noqa: ANN001
    from app.business.agents.tender.ports.task_port import FilesystemTenderTaskResultStore

    store = FilesystemTenderTaskResultStore(tmp_path)
    task_id = uuid4()
    result = _result()

    first = store.save(task_id=task_id, owner_subject="owner-1", result=result)
    second = store.save(task_id=task_id, owner_subject="owner-1", result=result)

    assert first == second == f"tender-result:{task_id}"
    assert list(tmp_path.glob("*.json")) == [tmp_path / f"{task_id}.json"]


def test_executor_confirms_cancellation_without_calling_tender() -> None:
    content = b"docx"
    reference = _reference(content)
    application = FakeTenderApplication(_result())
    executor = TenderTaskExecutor(
        application=application,
        input_reader=AttachmentTenderTaskInputReader(FakeAttachmentStorage(content, reference)),
        result_store=InMemoryTenderTaskResultStore(),
    )

    outcome = executor.execute(_context(reference, cancel=lambda: True))

    assert isinstance(outcome, TaskExecutionCancellation)
    assert application.commands == []
