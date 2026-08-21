from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from app.composition.interaction import build_agent_call_dispatcher
from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.modules.attachment import AttachmentAccessContext, AttachmentStoragePort
from app.modules.interaction.application.agent_call_policy import AgentCallPolicyValidator
from app.modules.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatcher,
)
from app.modules.interaction.domain.agent_call import StructuredAgentCall
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.modules.security.domain.principal import RequestPrincipal


def _capability(
    *,
    capability_type: str = "agent",
    confirmation_policy: str = "never",
) -> PlatformCapability:
    return PlatformCapability(
        code="agent.tender.generate_bid_skeleton",
        capability_type=capability_type,  # type: ignore[arg-type]
        description="生成投标文件骨架",
        input_schema={
            "type": "object",
            "properties": {"file_name": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("file_name",),
        confirmation_policy=confirmation_policy,  # type: ignore[arg-type]
        permission=("agent:tender:execute",),
        enabled=True,
        timeout_seconds=120,
        error_boundary="agent-runtime",
        dispatch_key="agent.tender.generate_bid_skeleton",
        retrieval_metadata={},
    )


def _call() -> StructuredAgentCall:
    return StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        inputs={"file_name": "投标文件.docx"},
        conversation_id="conversation-1",
        turn_id="turn-1",
        run_id="run-1",
    )


def _principal() -> RequestPrincipal:
    return RequestPrincipal(
        subject="user-1",
        permissions=frozenset({"agent:tender:execute"}),
        authenticated=True,
    )


def _approved(call: StructuredAgentCall) -> ApprovedCapabilityDispatch:
    return ApprovedCapabilityDispatch(
        proposal_id="proposal-1",
        capability_code=call.capability_code,
        dispatch_key="agent.tender.generate_bid_skeleton",
        inputs=dict(call.inputs),
    )


@dataclass
class SequenceCatalog:
    outcomes: list[PlatformCapability | None | Exception]
    calls: int = 0

    def get_available(
        self,
        code: str,  # noqa: ARG002
        *,
        permissions: Iterable[str] = (),  # noqa: ARG002
    ) -> PlatformCapability | None:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@dataclass
class RecordingRuntime:
    outcome: object
    calls: list[dict[str, object]] = field(default_factory=list)

    def execute(
        self,
        *,
        capability_code: str,
        dispatch_key: str,
        inputs: dict[str, object],
        permissions: Iterable[str] = (),
    ) -> object:
        self.calls.append(
            {
                "capability_code": capability_code,
                "dispatch_key": dispatch_key,
                "inputs": dict(inputs),
                "permissions": tuple(permissions),
            }
        )
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class AgentOutput(BaseModel):
    answer: str


_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _dispatcher(
    catalog: SequenceCatalog,
    runtime: RecordingRuntime,
    artifact_storage: AttachmentStoragePort | None = None,
) -> AgentCallDispatcher:
    return AgentCallDispatcher(
        catalog,  # type: ignore[arg-type]
        AgentCallPolicyValidator(catalog),  # type: ignore[arg-type]
        runtime,
        artifact_storage=artifact_storage,
    )


def test_dispatch_executes_authorized_call_once_and_preserves_association_ids() -> None:
    capability = _capability()
    catalog = SequenceCatalog([capability, capability])
    runtime = RecordingRuntime({"artifact": "bid-skeleton.docx"})

    result = _dispatcher(catalog, runtime).dispatch(
        AgentCallDispatchCommand(call=_call(), principal=_principal())
    )

    assert result.status == "completed"
    assert result.result is not None
    assert result.result.call_id == "call-1"
    assert result.result.conversation_id == "conversation-1"
    assert result.result.turn_id == "turn-1"
    assert result.result.run_id == "run-1"
    assert result.result.output == {"artifact": "bid-skeleton.docx"}
    assert result.error is None
    assert runtime.calls == [
        {
            "capability_code": capability.code,
            "dispatch_key": capability.dispatch_key,
            "inputs": {"file_name": "投标文件.docx"},
            "permissions": ("agent:tender:execute",),
        }
    ]


def test_dispatch_serializes_pydantic_runtime_output() -> None:
    capability = _capability()
    result = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(AgentOutput(answer="已生成")),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert result.status == "completed"
    assert result.result is not None
    assert result.result.output == {"answer": "已生成"}


def test_dispatch_does_not_call_runtime_when_confirmation_is_required() -> None:
    capability = _capability(confirmation_policy="always")
    runtime = RecordingRuntime({"unexpected": True})

    result = _dispatcher(SequenceCatalog([capability]), runtime).dispatch(
        AgentCallDispatchCommand(call=_call(), principal=_principal())
    )

    assert result.status == "confirmation_required"
    assert result.error is not None
    assert result.error.error_code == "CONFIRMATION_REQUIRED"
    assert runtime.calls == []


def test_dispatch_executes_confirmed_call_only_after_policy_authorization() -> None:
    capability = _capability(confirmation_policy="always")
    call = _call()
    runtime = RecordingRuntime({"artifact": "bid-skeleton.docx"})

    result = _dispatcher(SequenceCatalog([capability, capability]), runtime).dispatch(
        AgentCallDispatchCommand(
            call=call,
            principal=_principal(),
            approved_dispatch=_approved(call),
        )
    )

    assert result.status == "completed"
    assert len(runtime.calls) == 1


def test_dispatch_does_not_call_runtime_when_policy_rejects_or_catalog_is_unavailable() -> None:
    call = _call()
    non_agent = _capability(capability_type="chat")
    rejected_runtime = RecordingRuntime({"unexpected": True})
    rejected = _dispatcher(SequenceCatalog([non_agent]), rejected_runtime).dispatch(
        AgentCallDispatchCommand(call=call, principal=_principal())
    )

    unavailable_runtime = RecordingRuntime({"unexpected": True})
    unavailable = _dispatcher(
        SequenceCatalog([RuntimeError("catalog database password")]),
        unavailable_runtime,
    ).dispatch(AgentCallDispatchCommand(call=call, principal=_principal()))

    assert rejected.status == "rejected"
    assert rejected.error is not None
    assert rejected.error.error_code == "CAPABILITY_TYPE_NOT_AGENT"
    assert rejected_runtime.calls == []
    assert unavailable.status == "unavailable"
    assert unavailable.error is not None
    assert unavailable.error.error_code == "CAPABILITY_CATALOG_UNAVAILABLE"
    assert unavailable_runtime.calls == []


def test_dispatch_rechecks_catalog_before_runtime_execution() -> None:
    capability = _capability()
    runtime = RecordingRuntime({"unexpected": True})

    result = _dispatcher(SequenceCatalog([capability, None]), runtime).dispatch(
        AgentCallDispatchCommand(call=_call(), principal=_principal())
    )

    assert result.status == "rejected"
    assert result.error is not None
    assert result.error.error_code == "CAPABILITY_UNAVAILABLE"
    assert runtime.calls == []


def test_dispatch_maps_runtime_target_input_and_execution_failures_without_details() -> None:
    capability = _capability()

    target = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(LookupError("hidden target")),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))
    invalid_input = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(ValueError("raw validation detail")),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))
    execution = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(RuntimeError("provider secret token")),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert target.status == "failed"
    assert target.error is not None
    assert target.error.error_code == "DISPATCH_TARGET_UNAVAILABLE"
    assert invalid_input.status == "rejected"
    assert invalid_input.error is not None
    assert invalid_input.error.error_code == "DISPATCH_INPUT_INVALID"
    assert execution.status == "failed"
    assert execution.error is not None
    assert execution.error.error_code == "DISPATCH_EXECUTION_FAILED"
    assert "provider secret token" not in execution.error.message


def test_dispatch_rejects_non_object_or_non_serializable_runtime_output() -> None:
    capability = _capability()
    scalar = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime("not-an-object"),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))
    non_serializable = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime({"unsupported": object()}),
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert scalar.status == "failed"
    assert scalar.error is not None
    assert scalar.error.error_code == "AGENT_OUTPUT_INVALID"
    assert non_serializable.status == "failed"
    assert non_serializable.error is not None
    assert non_serializable.error.error_code == "AGENT_OUTPUT_INVALID"


def test_dispatch_stages_binary_artifact_as_controlled_resource(tmp_path: Path) -> None:
    capability = _capability()
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=(_DOCX_MEDIA_TYPE,),
    )
    result = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(
            {
                "artifacts": [
                    {
                        "file_name": "bid-skeleton.docx",
                        "media_type": _DOCX_MEDIA_TYPE,
                        "content": b"generated-docx-content",
                    }
                ]
            }
        ),
        artifact_storage=storage,
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert result.status == "completed"
    assert result.result is not None
    artifact = result.result.output["artifacts"][0]  # type: ignore[index]
    assert artifact["file_name"] == "bid-skeleton.docx"  # type: ignore[index]
    assert artifact["media_type"] == _DOCX_MEDIA_TYPE  # type: ignore[index]
    assert artifact["size"] == len(b"generated-docx-content")  # type: ignore[index]
    resource_id = artifact["resource_id"]  # type: ignore[index]
    assert isinstance(resource_id, str)
    assert len(resource_id) == 32
    assert "content" not in artifact  # type: ignore[operator]
    assert storage.read(
        resource_id,
        context=AttachmentAccessContext(subject="user-1", conversation_id="conversation-1"),
    ).content == b"generated-docx-content"


def test_dispatch_cleans_staged_artifacts_when_a_later_artifact_is_invalid(tmp_path: Path) -> None:
    capability = _capability()
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=(_DOCX_MEDIA_TYPE,),
    )
    result = _dispatcher(
        SequenceCatalog([capability, capability]),
        RecordingRuntime(
            {
                "artifacts": [
                    {
                        "file_name": "bid-skeleton.docx",
                        "media_type": _DOCX_MEDIA_TYPE,
                        "content": b"generated-docx-content",
                    },
                    {
                        "file_name": "unsafe.exe",
                        "media_type": "application/x-msdownload",
                        "content": b"not-allowed",
                    },
                ]
            }
        ),
        artifact_storage=storage,
    ).dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_code == "AGENT_ARTIFACT_STORE_FAILED"
    assert list(storage.attachment_root.iterdir()) == []


def test_composition_can_inject_agent_runtime_for_v2_dispatcher() -> None:
    capability = _capability()
    catalog = SequenceCatalog([capability, capability])
    runtime = RecordingRuntime({"artifact": "bid-skeleton.docx"})

    dispatcher = build_agent_call_dispatcher(
        catalog,  # type: ignore[arg-type]
        agent_runtime=lambda: runtime,
    )
    result = dispatcher.dispatch(AgentCallDispatchCommand(call=_call(), principal=_principal()))

    assert result.status == "completed"
    assert len(runtime.calls) == 1
