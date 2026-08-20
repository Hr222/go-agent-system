from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.interfaces.http.assemblers.interaction import gateway_response
from app.modules.attachment import AttachmentAccessContext
from app.modules.interaction.application.attachment_resolution import (
    CapabilityAttachmentResolver,
)
from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.gateway import (
    ControlledDispatcher,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.modules.interaction.domain.attachment import ResolvedAttachment
from app.modules.interaction.domain.capability import (
    CapabilityValidationError,
    PlatformCapability,
)
from app.modules.interaction.domain.intent import IntentAssessment
from app.modules.security.domain.principal import RequestPrincipal

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


class _ProvidedInputRecognition:
    def __init__(self, capability_code: str) -> None:
        self._capability_code = capability_code

    def recognize(self, command):  # noqa: ANN001
        return IntentAssessment(
            status="matched",
            capability_code=self._capability_code,
            extracted_inputs=dict(command.provided_inputs),
        )


class _RecordingHandler:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, inputs: dict[str, object]) -> object:
        self.calls.append(inputs)
        return {"status": "processed"}


def _storage(tmp_path: Path, **kwargs: object) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=("application/pdf", "image/png"),
        **kwargs,
    )


def _capability(
    *,
    capability_type: str = "policy_decision",
    max_count: int = 1,
    max_size_bytes: int = 1024,
    allowed_media_types: list[str] | None = None,
    dispatch_key: str = "document.process",
) -> PlatformCapability:
    attachment_schema: dict[str, object] = {
        "type": "string" if max_count == 1 else "array",
        "x-attachment": {
            "allowed_media_types": (
                allowed_media_types if allowed_media_types is not None else ["application/pdf"]
            ),
            "max_size_bytes": max_size_bytes,
            "max_count": max_count,
        },
    }
    if max_count > 1:
        attachment_schema["items"] = {"type": "string"}
    return PlatformCapability(
        code="document.process",
        capability_type=capability_type,  # type: ignore[arg-type]
        description="处理受控文档",
        input_schema={
            "type": "object",
            "properties": {"source_document": attachment_schema},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("source_document",),
        confirmation_policy="always",
        permission=(),
        enabled=True,
        timeout_seconds=120,
        error_boundary="document-v1",
        dispatch_key=dispatch_key,
        retrieval_metadata={},
    )


def _gateway(
    storage: FilesystemAttachmentStorage,
    capability: PlatformCapability,
    *,
    handler: _RecordingHandler | None = None,
    agent_calls: list[dict[str, object]] | None = None,
) -> tuple[IntentInteractionGateway, _RecordingHandler]:
    catalog = _Catalog(capability)
    recording_handler = handler or _RecordingHandler()

    def call_agent(
        _code: str,
        _dispatch_key: str,
        inputs: dict[str, object],
        _principal: RequestPrincipal,
    ) -> object:
        assert agent_calls is not None
        agent_calls.append(inputs)
        return {"status": "processed"}

    return (
        IntentInteractionGateway(
            candidate_retrieval=_ReadyCandidates(),  # type: ignore[arg-type]
            intent_recognition=_ProvidedInputRecognition(capability.code),  # type: ignore[arg-type]
            confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
            proposal_store=InMemoryPendingProposalStore(),
            dispatcher=ControlledDispatcher(
                catalog,  # type: ignore[arg-type]
                {capability.dispatch_key: recording_handler},
                agent_handler=call_agent if agent_calls is not None else None,
            ),
            attachment_resolver=CapabilityAttachmentResolver(storage),
        ),
        recording_handler,
    )


def _principal(subject: str = "owner") -> RequestPrincipal:
    return RequestPrincipal(subject=subject, authenticated=True)


def _stage(
    storage: FilesystemAttachmentStorage,
    *,
    media_type: str = "application/pdf",
    content: bytes = b"dynamic document",
    subject: str = "owner",
    conversation_id: UUID | None = None,
) -> str:
    return storage.stage_attachment(
        file_name="source.pdf",
        media_type=media_type,
        file_stream=BytesIO(content),
        context=AttachmentAccessContext(
            subject=subject,
            conversation_id=str(conversation_id) if conversation_id is not None else None,
        ),
    ).attachment_id


def _recognize(
    gateway: IntentInteractionGateway,
    *,
    attachment_input: object,
    subject: str = "owner",
    conversation_id: UUID | None = None,
):
    return gateway.recognize(
        GatewayRecognitionCommand(
            user_input="处理上传的文档",
            principal=_principal(subject),
            provided_inputs={"source_document": attachment_input},
            conversation_id=conversation_id,
        )
    )


def test_gateway_resolves_dynamic_attachment_to_server_only_input(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    attachment_id = _stage(storage, conversation_id=CONVERSATION_A)
    gateway, handler = _gateway(storage, _capability())

    result = _recognize(
        gateway,
        attachment_input=attachment_id,
        conversation_id=CONVERSATION_A,
    )

    assert result.status == "pending"
    assert result.proposal is not None
    resolved = result.proposal.inputs["source_document"]
    assert isinstance(resolved, ResolvedAttachment)
    assert resolved.content == b"dynamic document"
    assert resolved.reference.attachment_id == attachment_id
    assert "dynamic document" not in repr(resolved)
    assert "content" not in gateway_response(result).model_dump()
    assert handler.calls == []

    confirmed = gateway.confirm(
        GatewayConfirmationCommand(
            proposal_id=result.proposal.proposal_id,
            action="confirm",
            principal=_principal(),
        )
    )

    assert confirmed.status == "completed"
    assert isinstance(handler.calls[0]["source_document"], ResolvedAttachment)


def test_http_response_downgrades_internal_attachment_echo_to_safe_metadata(
    tmp_path: Path,
) -> None:
    storage = _storage(tmp_path)
    attachment_id = _stage(storage)
    gateway, _handler = _gateway(storage, _capability())
    recognized = _recognize(gateway, attachment_input=attachment_id)
    assert recognized.proposal is not None
    internal_attachment = recognized.proposal.inputs["source_document"]

    response = gateway_response(
        GatewayResult(
            status=recognized.status,
            message=recognized.message,
            proposal=recognized.proposal,
            execution_result={"attachment": internal_attachment},
        )
    ).model_dump()

    encoded = str(response)
    assert response["execution_result"] == {
        "attachment": recognized.proposal.inputs["source_document"].reference.public_dict()
    }
    assert "dynamic document" not in encoded
    assert "stored_path" not in encoded


def test_gateway_resolves_declared_attachment_collection(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    first_id = _stage(storage, content=b"first")
    second_id = _stage(storage, content=b"second")
    gateway, handler = _gateway(storage, _capability(max_count=2))

    result = _recognize(gateway, attachment_input=[first_id, second_id])

    assert result.status == "pending"
    assert result.proposal is not None
    resolved = result.proposal.inputs["source_document"]
    assert isinstance(resolved, tuple)
    assert [item.content for item in resolved] == [b"first", b"second"]
    assert all(isinstance(item, ResolvedAttachment) for item in resolved)
    assert handler.calls == []


@pytest.mark.parametrize(
    ("media_type", "content", "capability", "attachment_input", "error_code"),
    [
        (
            "image/png",
            b"image",
            _capability(),
            "dynamic",
            "ATTACHMENT_CONSTRAINT_VIOLATION",
        ),
        (
            "application/pdf",
            b"too-large",
            _capability(max_size_bytes=3),
            "dynamic",
            "ATTACHMENT_CONSTRAINT_VIOLATION",
        ),
        (
            "application/pdf",
            b"one",
            _capability(),
            ["dynamic", "dynamic"],
            "ATTACHMENT_INPUT_INVALID",
        ),
    ],
)
def test_gateway_rejects_attachment_constraint_violations_before_proposal(
    tmp_path: Path,
    media_type: str,
    content: bytes,
    capability: PlatformCapability,
    attachment_input: object,
    error_code: str,
) -> None:
    storage = _storage(tmp_path)
    attachment_id = _stage(storage, media_type=media_type, content=content)
    gateway, handler = _gateway(storage, capability)
    value = attachment_id if attachment_input == "dynamic" else [attachment_id, attachment_id]

    result = _recognize(gateway, attachment_input=value)

    assert result.status == "needs_clarification"
    assert result.error_code == error_code
    assert result.proposal is None
    assert handler.calls == []


@pytest.mark.parametrize(
    ("staged_subject", "staged_conversation", "request_subject", "request_conversation"),
    [
        ("owner", None, "other", None),
        ("owner", CONVERSATION_A, "owner", CONVERSATION_B),
    ],
)
def test_gateway_rejects_cross_subject_or_cross_conversation_attachment(
    tmp_path: Path,
    staged_subject: str,
    staged_conversation: UUID | None,
    request_subject: str,
    request_conversation: UUID | None,
) -> None:
    storage = _storage(tmp_path)
    attachment_id = _stage(
        storage,
        subject=staged_subject,
        conversation_id=staged_conversation,
    )
    gateway, handler = _gateway(storage, _capability())

    result = _recognize(
        gateway,
        attachment_input=attachment_id,
        subject=request_subject,
        conversation_id=request_conversation,
    )

    assert result.status == "needs_clarification"
    assert result.error_code == "ATTACHMENT_UNAVAILABLE"
    assert result.proposal is None
    assert handler.calls == []


def test_gateway_rejects_expired_attachment_without_calling_agent_runtime(tmp_path: Path) -> None:
    storage = _storage(tmp_path, retention_seconds=1)
    attachment_id = _stage(storage)
    storage.cleanup_expired(now=datetime.now(UTC) + timedelta(seconds=2))
    agent_calls: list[dict[str, object]] = []
    gateway, handler = _gateway(
        storage,
        _capability(
            capability_type="agent",
            dispatch_key="agent.document.process",
        ),
        agent_calls=agent_calls,
    )

    result = _recognize(gateway, attachment_input=attachment_id)

    assert result.status == "needs_clarification"
    assert result.error_code == "ATTACHMENT_UNAVAILABLE"
    assert result.proposal is None
    assert handler.calls == []
    assert agent_calls == []


def test_capability_rejects_incomplete_attachment_declaration() -> None:
    with pytest.raises(CapabilityValidationError, match="allowed_media_types"):
        _capability(allowed_media_types=[])
