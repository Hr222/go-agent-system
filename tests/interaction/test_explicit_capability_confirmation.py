from __future__ import annotations

import ast
from pathlib import Path

from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.gateway import InMemoryPendingProposalStore
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.interaction.domain.confirmation import ConfirmationProposal
from app.modules.interaction.domain.intent import IntentAssessment


def _capability(*, confirmation_policy: str = "always") -> PlatformCapability:
    return PlatformCapability(
        code="chat.create",
        capability_type="chat",
        description="Create a chat response.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("message",),
        confirmation_policy=confirmation_policy,  # type: ignore[arg-type]
        permission=(),
        enabled=True,
        timeout_seconds=120,
        error_boundary="confirmation-test",
        dispatch_key="llm.chat",
        retrieval_metadata={},
    )


class FakeCatalog:
    def __init__(self, capability: PlatformCapability | None) -> None:
        self.capability = capability
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def get_available(
        self,
        code: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> PlatformCapability | None:
        self.calls.append((code, permissions))
        if self.capability is None or self.capability.code != code:
            return None
        return self.capability


def _matched_assessment(
    *,
    inputs: dict[str, object] | None = None,
) -> IntentAssessment:
    return IntentAssessment(
        status="matched",
        capability_code="chat.create",
        extracted_inputs=inputs or {"message": "hello"},
        candidate_codes=["chat.create"],
    )


def test_unconfirmed_proposal_only_exposes_controlled_dispatch_data() -> None:
    confirmation = ExplicitCapabilityConfirmation(
        FakeCatalog(_capability()),  # type: ignore[arg-type]
        proposal_id_factory=lambda: "proposal-1",
    )

    pending = confirmation.create_proposal(_matched_assessment())

    assert pending.status == "pending"
    assert pending.approved_dispatch is None
    assert pending.proposal is not None
    assert pending.proposal.proposal_id == "proposal-1"
    assert pending.proposal.capability_code == "chat.create"
    assert pending.proposal.dispatch_key == "llm.chat"
    forbidden_fields = {"url", "class_name", "function_name", "executor", "agent_runtime"}
    assert not forbidden_fields.intersection(pending.proposal.model_dump())


def test_explicit_confirmation_produces_a_controlled_dispatch_only_after_approval() -> None:
    confirmation = ExplicitCapabilityConfirmation(
        FakeCatalog(_capability()),  # type: ignore[arg-type]
        proposal_id_factory=lambda: "proposal-1",
    )
    pending = confirmation.create_proposal(_matched_assessment())

    assert pending.proposal is not None
    confirmed = confirmation.respond(pending.proposal, "confirm")

    assert confirmed.status == "confirmed"
    assert confirmed.proposal is not None
    assert confirmed.proposal.state == "confirmed"
    assert confirmed.approved_dispatch is not None
    assert confirmed.approved_dispatch.model_dump() == {
        "proposal_id": "proposal-1",
        "capability_code": "chat.create",
        "dispatch_key": "llm.chat",
        "inputs": {"message": "hello"},
    }


def test_empty_unknown_and_cancelled_confirmation_never_approve() -> None:
    confirmation = ExplicitCapabilityConfirmation(
        FakeCatalog(_capability()),  # type: ignore[arg-type]
        proposal_id_factory=lambda: "proposal-1",
    )
    pending = confirmation.create_proposal(_matched_assessment())

    assert pending.proposal is not None
    empty = confirmation.respond(pending.proposal, "")
    unknown = confirmation.respond(pending.proposal, "maybe")
    cancelled = confirmation.respond(pending.proposal, "cancel")

    assert empty.status == "pending"
    assert empty.approved_dispatch is None
    assert unknown.status == "pending"
    assert unknown.error_code == "UNRECOGNIZED_CONFIRMATION_INPUT"
    assert unknown.approved_dispatch is None
    assert cancelled.status == "cancelled"
    assert cancelled.proposal is not None
    assert cancelled.approved_dispatch is None

    rejected = confirmation.respond(cancelled.proposal, "confirm")

    assert rejected.status == "rejected"
    assert rejected.error_code == "PROPOSAL_CANCELLED"
    assert rejected.approved_dispatch is None


def test_invalid_assessments_or_inputs_cannot_create_a_confirmation_proposal() -> None:
    confirmation = ExplicitCapabilityConfirmation(FakeCatalog(_capability()))  # type: ignore[arg-type]
    incomplete = IntentAssessment(status="needs_clarification", missing_fields=["message"])
    invalid_inputs = _matched_assessment(inputs={"message": 3})

    incomplete_result = confirmation.create_proposal(incomplete)
    invalid_input_result = confirmation.create_proposal(invalid_inputs)

    assert incomplete_result.status == "rejected"
    assert incomplete_result.error_code == "NO_MATCHED_INTENT"
    assert invalid_input_result.status == "rejected"
    assert invalid_input_result.error_code == "INPUT_VALIDATION_FAILED"


def test_never_confirmation_policy_cannot_create_a_proposal() -> None:
    confirmation = ExplicitCapabilityConfirmation(
        FakeCatalog(_capability(confirmation_policy="never")),  # type: ignore[arg-type]
    )

    result = confirmation.create_proposal(_matched_assessment())

    assert result.status == "rejected"
    assert result.error_code == "CONFIRMATION_NOT_REQUIRED"
    assert result.proposal is None


def test_pending_proposal_store_snapshots_saved_proposals_on_subject_mismatch() -> None:
    proposal = ConfirmationProposal(
        proposal_id="proposal-1",
        capability_code="chat.create",
        dispatch_key="llm.chat",
        inputs={"message": "original"},
        summary="Create a chat response.",
        confirmation_prompt="批准后将开始处理该请求。",
    )
    store = InMemoryPendingProposalStore()
    store.save(proposal, subject="owner")
    proposal.inputs["message"] = "tampered"

    assert store.consume("proposal-1", subject="other") is None

    consumed = store.consume("proposal-1", subject="owner")

    assert consumed is not None
    assert consumed.inputs == {"message": "original"}
    consumed.inputs["message"] = "mutated-after-consume"
    assert store.consume("proposal-1", subject="owner") is None


def test_confirmation_services_do_not_depend_on_execution_or_lifecycle_layers() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source_paths = (
        project_root / "app" / "modules" / "interaction" / "application" / "confirmation.py",
        project_root / "app" / "composition" / "intent.py",
    )
    imported_modules: set[str] = set()
    source_text = ""
    for source_path in source_paths:
        source_text += source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    forbidden_imports = (
        "app.modules.agent",
        "app.modules.online",
        "app.infrastructure.persistence",
    )
    assert not any(
        module.startswith(prefix) for module in imported_modules for prefix in forbidden_imports
    )
    assert "Conversation" not in source_text
    assert "background" not in source_text.lower()
