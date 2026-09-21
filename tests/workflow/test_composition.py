from __future__ import annotations

import pytest

from app.composition.workflow import build_registered_workflow_versions
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.workflow.domain import WorkflowValidationError


class Catalog:
    def __init__(self, capability: PlatformCapability | None) -> None:
        self.capability = capability

    def get_available(self, code: str, *, permissions=()):
        if self.capability is None or code != self.capability.code:
            return None
        if set(self.capability.permission).issubset(set(permissions)):
            return self.capability
        return None


def _tender_capability() -> PlatformCapability:
    return PlatformCapability(
        code="tender.generate_bid_skeleton",
        capability_type="agent",
        description="Tender",
        input_schema={"properties": {"source_document": {"type": "string"}}},
        output_schema={
            "properties": {"analysis": {"type": "object"}, "artifacts": {"type": "array"}}
        },
        required_fields=("source_document",),
        confirmation_policy="always",
        permission=("agent:tender:execute",),
        enabled=True,
        timeout_seconds=60,
        error_boundary="tender-v1",
        dispatch_key="agent.tender.generate_bid_skeleton",
        retrieval_metadata={},
    )


def test_composition_registers_only_fixed_tender_workflow_version() -> None:
    registry = build_registered_workflow_versions(Catalog(_tender_capability()))

    version = registry.get("tender-generation", "v1")

    assert version is not None
    assert version.nodes[0].capability_code == "tender.generate_bid_skeleton"
    assert registry.get("unregistered", "v1") is None


def test_composition_rejects_missing_tender_capability_binding() -> None:
    with pytest.raises(WorkflowValidationError, match="未注册或未启用"):
        build_registered_workflow_versions(Catalog(None))
