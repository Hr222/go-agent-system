from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.modules.interaction.application.agent_call_policy import (
    AgentCallPolicyCommand,
    AgentCallPolicyValidator,
)
from app.modules.interaction.domain.agent_call import StructuredAgentCall
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.modules.security.domain.principal import RequestPrincipal


def _capability(
    *,
    capability_type: str = "agent",
    confirmation_policy: str = "always",
    permission: tuple[str, ...] = (),
    enabled: bool = True,
) -> PlatformCapability:
    return PlatformCapability(
        code="agent.tender.generate_bid_skeleton",
        capability_type=capability_type,  # type: ignore[arg-type]
        description="生成投标文件骨架。",
        input_schema={
            "type": "object",
            "properties": {"file_name": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("file_name",),
        confirmation_policy=confirmation_policy,  # type: ignore[arg-type]
        permission=permission,
        enabled=enabled,
        timeout_seconds=120,
        error_boundary="agent-policy-test",
        dispatch_key="agent.tender.generate_bid_skeleton",
        retrieval_metadata={},
    )


def _call(*, inputs: dict[str, object] | None = None) -> StructuredAgentCall:
    return StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        inputs=inputs or {"file_name": "招标文件.docx"},
        conversation_id="conversation-1",
        turn_id="turn-1",
    )


def _principal(*, permissions: frozenset[str] = frozenset()) -> RequestPrincipal:
    return RequestPrincipal(
        subject="user-1",
        permissions=permissions,
        authenticated=True,
    )


@dataclass
class FakeCatalog:
    capability: PlatformCapability | None
    fail: bool = False
    calls: list[tuple[str, tuple[str, ...]]] | None = None

    def get_available(
        self,
        code: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> PlatformCapability | None:
        if self.calls is None:
            self.calls = []
        self.calls.append((code, permissions))
        if self.fail:
            raise RuntimeError("catalog details must not escape")
        if self.capability is None or self.capability.code != code:
            return None
        if not self.capability.enabled:
            return None
        if not set(self.capability.permission).issubset(permissions):
            return None
        return self.capability


def _validator(
    *,
    capability: PlatformCapability | None = None,
    fail: bool = False,
) -> AgentCallPolicyValidator:
    return AgentCallPolicyValidator(
        FakeCatalog(capability or _capability(), fail=fail),  # type: ignore[arg-type]
    )


def _approved(call: StructuredAgentCall) -> ApprovedCapabilityDispatch:
    return ApprovedCapabilityDispatch(
        proposal_id="proposal-1",
        capability_code=call.capability_code,
        dispatch_key="agent.tender.generate_bid_skeleton",
        inputs=dict(call.inputs),
    )


def test_policy_requires_confirmation_for_always_and_accepts_matching_approval() -> None:
    validator = _validator()
    command = AgentCallPolicyCommand(call=_call(), principal=_principal())

    pending = validator.validate(command)

    assert pending.status == "confirmation_required"
    assert pending.error_code == "CONFIRMATION_REQUIRED"

    authorized = validator.validate(
        AgentCallPolicyCommand(
            call=command.call,
            principal=command.principal,
            approved_dispatch=_approved(command.call),
        )
    )

    assert authorized.status == "authorized"
    assert authorized.error_code is None


@pytest.mark.parametrize("policy", ["conditional", "never"])
def test_policy_handles_conditional_and_never_confirmation_policies(policy: str) -> None:
    validator = _validator(capability=_capability(confirmation_policy=policy))

    result = validator.validate(
        AgentCallPolicyCommand(call=_call(), principal=_principal())
    )

    if policy == "conditional":
        assert result.status == "confirmation_required"
        assert result.error_code == "CONFIRMATION_REQUIRED"
    else:
        assert result.status == "authorized"
        assert result.error_code is None


@pytest.mark.parametrize(
    ("approved_factory", "expected_code"),
    [
        (
            lambda call: ApprovedCapabilityDispatch(
                proposal_id="proposal-1",
                capability_code="agent.other",
                dispatch_key="agent.tender.generate_bid_skeleton",
                inputs=dict(call.inputs),
            ),
            "APPROVAL_MISMATCH",
        ),
        (
            lambda call: ApprovedCapabilityDispatch(
                proposal_id="proposal-1",
                capability_code=call.capability_code,
                dispatch_key="agent.other",
                inputs=dict(call.inputs),
            ),
            "APPROVAL_MISMATCH",
        ),
        (
            lambda call: ApprovedCapabilityDispatch(
                proposal_id="proposal-1",
                capability_code=call.capability_code,
                dispatch_key="agent.tender.generate_bid_skeleton",
                inputs={"file_name": "另一个文件.docx"},
            ),
            "APPROVAL_MISMATCH",
        ),
    ],
)
def test_policy_rejects_non_matching_approval(approved_factory, expected_code: str) -> None:  # noqa: ANN001
    call = _call()
    result = _validator().validate(
        AgentCallPolicyCommand(
            call=call,
            principal=_principal(),
            approved_dispatch=approved_factory(call),
        )
    )

    assert result.status == "rejected"
    assert result.error_code == expected_code


def test_policy_rejects_invalid_capability_type_inputs_and_access() -> None:
    non_agent = _validator(capability=_capability(capability_type="chat")).validate(
        AgentCallPolicyCommand(call=_call(), principal=_principal())
    )
    invalid_inputs = _validator().validate(
        AgentCallPolicyCommand(
            call=_call(inputs={"file_name": 123}),
            principal=_principal(),
        )
    )
    protected = _validator(
        capability=_capability(permission=("agent:tender:execute",))
    ).validate(AgentCallPolicyCommand(call=_call(), principal=_principal()))
    disabled = _validator(capability=_capability(enabled=False)).validate(
        AgentCallPolicyCommand(call=_call(), principal=_principal())
    )

    assert non_agent.error_code == "CAPABILITY_TYPE_NOT_AGENT"
    assert invalid_inputs.error_code == "INPUT_VALIDATION_FAILED"
    assert protected.error_code == "CAPABILITY_UNAVAILABLE"
    assert disabled.error_code == "CAPABILITY_UNAVAILABLE"


def test_policy_maps_catalog_failures_without_execution_or_provider_details() -> None:
    result = _validator(fail=True).validate(
        AgentCallPolicyCommand(call=_call(), principal=_principal())
    )

    assert result.status == "unavailable"
    assert result.error_code == "CAPABILITY_CATALOG_UNAVAILABLE"
    assert "catalog details" not in result.message


def test_policy_returns_a_deep_copied_call_and_does_not_import_execution_layers() -> None:
    call = _call()
    result = _validator().validate(
        AgentCallPolicyCommand(call=call, principal=_principal())
    )

    assert result.call is not call
    assert result.call.model_dump() == call.model_dump()
    assert result.status == "confirmation_required"

    source_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "modules"
        / "interaction"
        / "application"
        / "agent_call_policy.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        module.startswith(prefix)
        for module in imported_modules
        for prefix in (
            "app.modules.agent",
            "app.modules.online",
            "app.infrastructure",
            "app.interfaces",
        )
    )
