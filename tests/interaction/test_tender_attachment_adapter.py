from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from docx import Document

from app.business.agents.tender.contracts import TenderGenerateSkeletonCommand
from app.composition.interaction import build_agent_runtime
from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.platform.attachment import AttachmentAccessContext
from app.platform.interaction.application.attachment_resolution import (
    CapabilityAttachmentResolver,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.gateway import (
    ControlledDispatcher,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.platform.interaction.domain.attachment import (
    ResolvedAttachment,
    attachment_field_declarations,
)
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.interaction.domain.intent import IntentAssessment
from app.platform.security.domain.principal import RequestPrincipal

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CONVERSATION_A = UUID("00000000-0000-0000-0000-000000000001")
CONVERSATION_B = UUID("00000000-0000-0000-0000-000000000002")


class _Catalog:
    def __init__(self, capability: PlatformCapability) -> None:
        self.capability = capability

    def get_available(
        self,
        code: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> PlatformCapability | None:
        del permissions
        return self.capability if code == self.capability.code else None


class _ReadyCandidates:
    def is_ready(self, *, permissions: tuple[str, ...] = ()) -> bool:
        del permissions
        return True

    def refresh(self, *, permissions: tuple[str, ...] = ()) -> None:
        del permissions
        raise AssertionError("ready candidates must not refresh")


class _TenderRecognition:
    def recognize(self, command):  # noqa: ANN001
        return IntentAssessment(
            status="matched",
            capability_code="tender.generate_bid_skeleton",
            extracted_inputs=dict(command.provided_inputs),
        )


@dataclass
class FakeTenderApplication:
    commands: list[TenderGenerateSkeletonCommand] = field(default_factory=list)

    def execute(self, command: TenderGenerateSkeletonCommand) -> object:
        self.commands.append(command)
        return {"status": "processed", "file_name": command.file_name}


def _capability() -> PlatformCapability:
    return PlatformCapability(
        code="tender.generate_bid_skeleton",
        capability_type="agent",
        description="读取招标文件并生成投标骨架。",
        input_schema={
            "type": "object",
            "properties": {
                "source_document": {
                    "type": "string",
                    "x-attachment": {
                        "allowed_media_types": [DOCX_MEDIA_TYPE],
                        "max_size_bytes": 50 * 1024 * 1024,
                        "max_count": 1,
                    },
                },
                "user_focus": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("source_document",),
        confirmation_policy="always",
        permission=(),
        enabled=True,
        timeout_seconds=300,
        error_boundary="tender-agent-v1",
        dispatch_key="agent.tender.generate_bid_skeleton",
        retrieval_metadata={},
    )


def _storage(tmp_path: Path, **kwargs: object) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=(DOCX_MEDIA_TYPE, "application/pdf"),
        **kwargs,
    )


def _docx_content() -> bytes:
    document = Document()
    document.add_paragraph("动态招标文件附件")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _stage(
    storage: FilesystemAttachmentStorage,
    *,
    file_name: str = "tender.docx",
    media_type: str = DOCX_MEDIA_TYPE,
    content: bytes | None = None,
    subject: str = "owner",
    conversation_id: UUID | None = None,
) -> str:
    resolved_content = content if content is not None else _docx_content()
    return storage.stage_attachment(
        file_name=file_name,
        media_type=media_type,
        file_stream=BytesIO(resolved_content),
        context=AttachmentAccessContext(
            subject=subject,
            conversation_id=str(conversation_id) if conversation_id is not None else None,
        ),
    ).attachment_id


def _principal(subject: str = "owner") -> RequestPrincipal:
    return RequestPrincipal(subject=subject, authenticated=True)


def _gateway(
    storage: FilesystemAttachmentStorage,
    application: FakeTenderApplication,
):
    catalog = _Catalog(_capability())
    runtime = build_agent_runtime(
        catalog,  # type: ignore[arg-type]
        tender_application=lambda: application,  # type: ignore[arg-type]
    )

    def call_agent(
        capability_code: str,
        dispatch_key: str,
        inputs: dict[str, object],
        principal: RequestPrincipal,
    ) -> object:
        return runtime.execute(
            capability_code=capability_code,
            dispatch_key=dispatch_key,
            inputs=inputs,
            permissions=principal.permission_tuple(),
        )

    gateway = IntentInteractionGateway(
        candidate_retrieval=_ReadyCandidates(),  # type: ignore[arg-type]
        intent_recognition=_TenderRecognition(),  # type: ignore[arg-type]
        confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=ControlledDispatcher(catalog, {}, agent_handler=call_agent),  # type: ignore[arg-type]
        attachment_resolver=CapabilityAttachmentResolver(storage),
    )
    return gateway, runtime


def _recognize(
    gateway: IntentInteractionGateway,
    *,
    attachment_id: str,
    subject: str = "owner",
    conversation_id: UUID | None = None,
):
    return gateway.recognize(
        GatewayRecognitionCommand(
            user_input="根据这个招标文件生成投标骨架",
            principal=_principal(subject),
            provided_inputs={
                "source_document": attachment_id,
                "user_focus": "关注资格审查材料",
            },
            conversation_id=conversation_id,
        )
    )


def test_tender_attachment_catalog_declares_single_docx_source_document() -> None:
    declaration = attachment_field_declarations(_capability().input_schema)

    assert declaration[0].field_name == "source_document"
    assert declaration[0].allowed_media_types == (DOCX_MEDIA_TYPE,)
    assert declaration[0].max_size_bytes == 50 * 1024 * 1024
    assert declaration[0].max_count == 1

    sql_dir = Path(__file__).resolve().parents[2] / "sql"
    seed = (sql_dir / "005_platform_capability.sql").read_text(encoding="utf-8")
    migration = (sql_dir / "009_tender_attachment_capability.sql").read_text(encoding="utf-8")
    tender_seed = seed.split("'tender.generate_bid_skeleton'", maxsplit=1)[1].split(
        "),", maxsplit=1
    )[0]

    assert '"source_document"' in tender_seed
    assert '"x-attachment"' in tender_seed
    assert DOCX_MEDIA_TYPE in tender_seed
    assert '"max_size_bytes":52428800' in tender_seed
    assert '"max_count":1' in tender_seed
    assert "content_base64" not in tender_seed
    assert "UPDATE platform_capability" in migration
    assert "IS DISTINCT FROM" in migration


def test_dynamic_docx_attachment_waits_for_confirmation_before_tender_execution(
    tmp_path: Path,
) -> None:
    source_content = _docx_content()
    storage = _storage(tmp_path)
    attachment_id = _stage(
        storage,
        content=source_content,
        conversation_id=CONVERSATION_A,
    )
    application = FakeTenderApplication()
    gateway, runtime = _gateway(storage, application)

    recognized = _recognize(
        gateway,
        attachment_id=attachment_id,
        conversation_id=CONVERSATION_A,
    )

    assert recognized.status == "pending"
    assert recognized.proposal is not None
    source_document = recognized.proposal.inputs["source_document"]
    assert isinstance(source_document, ResolvedAttachment)
    assert source_document.reference.attachment_id == attachment_id
    assert source_document.reference.file_name == "tender.docx"
    assert source_document.content == source_content
    assert source_document.content.startswith(b"PK")
    assert "content_base64" not in recognized.proposal.inputs
    assert application.commands == []

    confirmation = gateway.confirm_dialogue_agent(
        GatewayConfirmationCommand(
            proposal_id=recognized.proposal.proposal_id,
            action="confirm",
            principal=_principal(),
        )
    )

    assert confirmation.status == "confirmed"
    assert confirmation.approved_dispatch is not None
    completed = runtime.execute(
        capability_code=confirmation.approved_dispatch.capability_code,
        dispatch_key=confirmation.approved_dispatch.dispatch_key,
        inputs=confirmation.approved_dispatch.inputs,
        permissions=_principal().permission_tuple(),
    )
    assert completed == {"status": "processed", "file_name": "tender.docx"}
    assert application.commands == [
        TenderGenerateSkeletonCommand(
            file_name="tender.docx",
            content=source_content,
            user_focus="关注资格审查材料",
        )
    ]


@pytest.mark.parametrize(
    ("scenario", "expected_error_code"),
    [
        ("non_docx", "ATTACHMENT_CONSTRAINT_VIOLATION"),
        ("expired", "ATTACHMENT_UNAVAILABLE"),
        ("other_subject", "ATTACHMENT_UNAVAILABLE"),
        ("other_conversation", "ATTACHMENT_UNAVAILABLE"),
    ],
)
def test_tender_attachment_rejections_do_not_execute_tender(
    tmp_path: Path,
    scenario: str,
    expected_error_code: str,
) -> None:
    storage = (
        _storage(tmp_path, retention_seconds=1)
        if scenario == "expired"
        else _storage(tmp_path)
    )
    staged_conversation = CONVERSATION_A if scenario == "other_conversation" else None
    attachment_id = _stage(
        storage,
        file_name="source.pdf" if scenario == "non_docx" else "tender.docx",
        media_type="application/pdf" if scenario == "non_docx" else DOCX_MEDIA_TYPE,
        conversation_id=staged_conversation,
    )
    if scenario == "expired":
        storage.cleanup_expired(now=datetime.now(UTC) + timedelta(seconds=2))

    application = FakeTenderApplication()
    gateway, _runtime = _gateway(storage, application)
    recognized = _recognize(
        gateway,
        attachment_id=attachment_id,
        subject="other" if scenario == "other_subject" else "owner",
        conversation_id=CONVERSATION_B if scenario == "other_conversation" else None,
    )

    assert recognized.status == "needs_clarification"
    assert recognized.error_code == expected_error_code
    assert recognized.proposal is None
    assert application.commands == []
