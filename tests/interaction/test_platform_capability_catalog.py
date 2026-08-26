from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.business.online.application.policy_decision import PolicyDecisionApplicationService
from app.composition.interaction import build_capability_dispatch_registry
from app.composition.root import ApplicationContainer
from app.infrastructure.persistence.models.platform_capability import PlatformCapabilityRecord
from app.infrastructure.persistence.repositories.platform_capability_repository import (
    PlatformCapabilityRepository,
)
from app.platform.agent.runtime import AgentRuntime
from app.platform.interaction.application.catalog import PlatformCapabilityCatalog
from app.platform.interaction.application.dispatch import (
    CapabilityDispatchBinding,
    CapabilityDispatchConfigurationError,
    CapabilityDispatchRegistry,
)
from app.platform.interaction.domain.capability import (
    CapabilityPrincipal,
    PlatformCapability,
)
from tests.support.db_test_utils import SchemaHarness


def _record(
    code: str,
    *,
    capability_type: str = "agent",
    dispatch_key: str | None = None,
    permission: list[str] | None = None,
    enabled: bool = True,
) -> PlatformCapabilityRecord:
    return PlatformCapabilityRecord(
        code=code,
        capability_type=capability_type,
        description=f"{code} description",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        output_schema={"type": "object"},
        required_fields=["message"],
        confirmation_policy="always",
        permission=permission or [],
        enabled=enabled,
        timeout_seconds=120,
        error_boundary="test-boundary",
        dispatch_key=dispatch_key or code,
        retrieval_metadata={"aliases": [code]},
    )


def test_repository_filters_disabled_and_permissioned_capabilities() -> None:
    harness = SchemaHarness("platform_catalog")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            session.add_all(
                [
                    _record("agent.public"),
                    _record("agent.private", permission=["agent:run"]),
                    _record("agent.disabled", enabled=False),
                    _record("chat.general", capability_type="chat"),
                ]
            )
            session.commit()

            repository = PlatformCapabilityRepository(session)

            assert [
                item.code
                for item in repository.list_available(capability_type="agent")
            ] == ["agent.public"]
            assert [
                item.code
                for item in repository.list_available(
                    capability_type="agent",
                    principal=CapabilityPrincipal.from_permissions({"agent:run"}),
                )
            ] == ["agent.private", "agent.public"]
            assert [item.code for item in repository.list_available()] == [
                "agent.public",
                "chat.general",
            ]
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_platform_catalog_rejects_unknown_or_mismatched_dispatch_keys() -> None:
    valid = PlatformCapability(
        code="agent.tender",
        capability_type="agent",
        description="Tender",
        input_schema={},
        output_schema={},
        required_fields=(),
        confirmation_policy="always",
        permission=(),
        enabled=True,
        timeout_seconds=120,
        error_boundary="tender",
        dispatch_key="agent.tender",
        retrieval_metadata={},
    )

    class FakeRepository:
        def __init__(self, capability: PlatformCapability) -> None:
            self.capability = capability

        def list_registered(self) -> tuple[PlatformCapability, ...]:
            return (self.capability,)

        def list_available(self, **kwargs):  # noqa: ANN003
            return (self.capability,)

        def get_available(self, code: str, **kwargs):  # noqa: ANN003
            return self.capability if code == self.capability.code else None

    catalog = PlatformCapabilityCatalog(
        FakeRepository(valid),
        CapabilityDispatchRegistry(
            (
                CapabilityDispatchBinding(
                    dispatch_key="agent.tender",
                    capability_type="chat",
                    use_case_type=object,
                ),
            )
        ),
    )

    with pytest.raises(CapabilityDispatchConfigurationError, match="不匹配"):
        catalog.validate_registered()

    unknown = replace(valid, dispatch_key="agent.unknown")
    with pytest.raises(CapabilityDispatchConfigurationError, match="未注册"):
        PlatformCapabilityCatalog(
            FakeRepository(unknown),
            CapabilityDispatchRegistry(),
        ).validate_registered()


def test_dispatch_registry_rejects_executable_address() -> None:
    with pytest.raises(CapabilityDispatchConfigurationError, match="分发键格式无效"):
        CapabilityDispatchRegistry(
            (
                CapabilityDispatchBinding(
                    dispatch_key="https://example.com/run",
                    capability_type="agent",
                    use_case_type=object,
                ),
            )
        )


def test_agent_runtime_consumes_only_agent_catalog_entries() -> None:
    harness = SchemaHarness("agent_runtime")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            session.add_all(
                [
                    _record(
                        "tender.generate_bid_skeleton",
                        dispatch_key="agent.tender.generate_bid_skeleton",
                    ),
                    _record(
                        "chat.general",
                        capability_type="chat",
                        dispatch_key="llm.chat",
                    ),
                ]
            )
            session.commit()
            repository = PlatformCapabilityRepository(session)
            catalog = PlatformCapabilityCatalog(repository, build_capability_dispatch_registry())

            runtime = AgentRuntime(catalog)

            assert [item.code for item in runtime.list_capabilities()] == [
                "tender.generate_bid_skeleton"
            ]
            assert runtime.get_capability("chat.general") is None
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_capability_code_is_unique() -> None:
    harness = SchemaHarness("platform_unique")
    harness.create_schema()
    try:
        session = harness.session_local()
        try:
            session.add_all([_record("agent.same"), _record("agent.same")])
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
        finally:
            session.close()
    finally:
        harness.drop_schema()


def test_container_injects_catalog_as_the_agent_runtime_source() -> None:
    capability = PlatformCapability(
        code="agent.tender",
        capability_type="agent",
        description="Tender",
        input_schema={},
        output_schema={},
        required_fields=(),
        confirmation_policy="always",
        permission=(),
        enabled=True,
        timeout_seconds=120,
        error_boundary="tender",
        dispatch_key="agent.tender",
        retrieval_metadata={},
    )

    class FakeCatalog:
        def list_available(self, **kwargs):  # noqa: ANN003
            return (capability,) if kwargs["capability_type"] == "agent" else ()

        def get_available(self, code: str, **kwargs):  # noqa: ANN003
            return capability if code == capability.code else None

    catalog = FakeCatalog()
    container = ApplicationContainer(capability_catalog=catalog)

    assert container.agent_runtime().capability_catalog is catalog
    assert container.agent_runtime().list_capabilities() == (capability,)


def test_policy_review_seed_matches_the_policy_decision_command_contract() -> None:
    seed = (Path(__file__).resolve().parents[2] / "sql" / "005_platform_capability.sql").read_text(
        encoding="utf-8"
    )

    assert "\"answers\"" not in seed
    assert "'[\"scenario_code\",\"submitted_materials\"]'" in seed
    for field_name in (
        "scenario_code",
        "submitted_materials",
        "top_k",
        "document_id",
        "include_history",
    ):
        assert f'\"{field_name}\"' in seed

    capability = PlatformCapability(
        code="policy.review",
        capability_type="policy_decision",
        description="政策判断",
        input_schema={
            "type": "object",
            "properties": {
                "scenario_code": {"type": "string"},
                "submitted_materials": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer", "minimum": 1},
                "document_id": {"type": ["integer", "null"]},
                "include_history": {"type": "boolean"},
            },
        },
        output_schema={"type": "object"},
        required_fields=("scenario_code", "submitted_materials"),
        confirmation_policy="always",
        permission=(),
        enabled=True,
        timeout_seconds=120,
        error_boundary="policy-decision-v1",
        dispatch_key="online.policy_decision.review",
        retrieval_metadata={},
    )

    binding = build_capability_dispatch_registry().validate(capability)

    assert binding.use_case_type is PolicyDecisionApplicationService


def test_chat_general_seed_and_migration_disable_confirmation() -> None:
    sql_dir = Path(__file__).resolve().parents[2] / "sql"
    seed = (sql_dir / "005_platform_capability.sql").read_text(encoding="utf-8")
    migration = (sql_dir / "006_chat_general_confirmation_policy.sql").read_text(
        encoding="utf-8"
    )

    chat_seed = seed.split("'chat.general'", maxsplit=1)[1].split("),", maxsplit=1)[0]
    assert "'never'" in chat_seed
    assert "UPDATE platform_capability" in migration
    assert "confirmation_policy = 'never'" in migration
    assert "IS DISTINCT FROM 'never'" in migration
