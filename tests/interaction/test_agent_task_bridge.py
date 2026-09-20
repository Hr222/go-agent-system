from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterable

from app.platform.interaction.application.agent_call_policy import AgentCallPolicyValidator
from app.platform.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatcher,
)
from app.platform.interaction.application.agent_task_bridge import (
    AgentTaskBridge,
    AgentTaskExecutionStrategyRouter,
    AgentTaskProfileRegistry,
    CanonicalAgentTaskInputSnapshotProvider,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.interaction.ports.agent_execution import (
    AgentExecutionCommand,
    AgentExecutionOutcome,
)
from app.platform.interaction.ports.agent_task_bridge import (
    AgentTaskInputSnapshot,
    AgentTaskProfile,
    AgentTaskRoute,
)
from app.platform.security.domain import RequestPrincipal
from app.platform.task.application import (
    TaskLifecycleService,
    TrustedTaskSubmissionProfile,
    TrustedTaskSubmissionService,
)
from tests.task.in_memory_repository import InMemoryTaskRepository


def _capability(*, enabled: bool = True) -> PlatformCapability:
    return PlatformCapability(
        code="agent.demo.async",
        capability_type="agent",
        description="异步测试 Agent",
        input_schema={
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "owner": {"type": "string"},
                "executor": {"type": "string"},
            },
        },
        output_schema={"type": "object"},
        required_fields=(),
        confirmation_policy="never",
        permission=(),
        enabled=enabled,
        timeout_seconds=30,
        error_boundary="agent-runtime",
        dispatch_key="agent.demo.async",
        retrieval_metadata={},
    )


def _call(call_id: str = "call-1") -> StructuredAgentCall:
    return StructuredAgentCall(
        call_id=call_id,
        capability_code="agent.demo.async",
        inputs={
            "task_type": "client-controlled-value",
            "owner": "other-user",
            "executor": "client.executor",
        },
    )


def _principal() -> RequestPrincipal:
    return RequestPrincipal(subject="owner-1", authenticated=True)


@dataclass
class SnapshotProvider:
    fingerprints: list[str]
    snapshot_reference: str | None = None
    calls: list[StructuredAgentCall] = field(default_factory=list)

    def snapshot(
        self,
        call: StructuredAgentCall,
        profile: AgentTaskProfile,
    ) -> AgentTaskInputSnapshot:
        self.calls.append(call)
        return AgentTaskInputSnapshot(
            input_fingerprint=self.fingerprints.pop(0),
            snapshot_reference=self.snapshot_reference,
            display_metadata={"title": "合成异步任务"},
        )


@dataclass
class RecordingStrategy:
    outcome: AgentExecutionOutcome
    calls: list[AgentExecutionCommand] = field(default_factory=list)

    def execute(self, command: AgentExecutionCommand) -> AgentExecutionOutcome:
        self.calls.append(command)
        return self.outcome


def _bridge(
    repository: InMemoryTaskRepository,
    snapshot_provider: SnapshotProvider,
) -> tuple[AgentTaskBridge, AgentTaskProfileRegistry]:
    task_profile = TrustedTaskSubmissionProfile(
        task_type="agent.demo.async",
        max_attempts=2,
        allow_manual_retry=False,
        display_metadata_fields=("title", "snapshot_reference"),
    )
    submission = TrustedTaskSubmissionService(
        TaskLifecycleService(
            repository,
            clock=lambda: datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
        ),
        task_profile,
    )
    route = AgentTaskRoute(
        profile=AgentTaskProfile(
            capability_code="agent.demo.async",
            task_type=task_profile.task_type,
            max_attempts=task_profile.max_attempts,
            allow_manual_retry=task_profile.allow_manual_retry,
            display_metadata_fields=task_profile.display_metadata_fields,
        ),
        submission=submission,
    )
    registry = AgentTaskProfileRegistry((route,))
    return AgentTaskBridge(registry, snapshot_provider), registry


def _command(capability: PlatformCapability | None = None) -> AgentExecutionCommand:
    selected = capability or _capability()
    return AgentExecutionCommand(call=_call(), capability=selected, principal=_principal())


def test_bridge_submits_fixed_task_and_returns_opaque_reference() -> None:
    repository = InMemoryTaskRepository()
    bridge, _ = _bridge(repository, SnapshotProvider(["fingerprint-1"]))

    outcome = bridge.execute(_command())

    assert outcome.status == "accepted"
    assert outcome.execution_reference is not None
    assert outcome.execution_reference.startswith("task:")
    assert len(repository._tasks) == 1
    task = next(iter(repository._tasks.values()))
    assert task.owner_subject == "owner-1"
    assert task.task_type == "agent.demo.async"
    assert task.max_attempts == 2
    assert task.allow_manual_retry is False
    assert task.display_metadata == {"title": "合成异步任务"}
    assert task.idempotency_key == "agent:agent.demo.async:call-1"


def test_bridge_passes_snapshot_reference_only_through_internal_task_metadata() -> None:
    repository = InMemoryTaskRepository()
    bridge, _ = _bridge(
        repository,
        SnapshotProvider(["fingerprint-1"], snapshot_reference="attachment-opaque-1"),
    )

    outcome = bridge.execute(_command())

    assert outcome.status == "accepted"
    task = next(iter(repository._tasks.values()))
    assert task.display_metadata["snapshot_reference"] == "attachment-opaque-1"
    assert "snapshot_reference" not in repr(task.events)
    assert outcome.execution_reference == f"task:{task.id}"


def test_bridge_replay_returns_same_task_without_new_event() -> None:
    repository = InMemoryTaskRepository()
    bridge, _ = _bridge(repository, SnapshotProvider(["fingerprint-1", "fingerprint-1"]))

    first = bridge.execute(_command())
    replay = bridge.execute(_command())

    assert replay.execution_reference == first.execution_reference
    task = next(iter(repository._tasks.values()))
    assert len(task.events) == 1


def test_route_rejects_submission_policy_that_differs_from_async_profile() -> None:
    repository = InMemoryTaskRepository()
    submission = TrustedTaskSubmissionService(
        TaskLifecycleService(repository),
        TrustedTaskSubmissionProfile(task_type="agent.demo.actual", max_attempts=1),
    )
    profile = AgentTaskProfile(
        capability_code="agent.demo.async",
        task_type="agent.demo.expected",
        max_attempts=1,
    )

    try:
        AgentTaskRoute(profile=profile, submission=submission)
    except ValueError as exc:
        assert "不一致" in str(exc)
    else:
        raise AssertionError("不一致的提交策略必须被拒绝")


def test_bridge_maps_same_call_with_different_input_to_stable_conflict() -> None:
    repository = InMemoryTaskRepository()
    bridge, _ = _bridge(repository, SnapshotProvider(["fingerprint-1", "fingerprint-2"]))

    assert bridge.execute(_command()).status == "accepted"
    conflict = bridge.execute(_command())

    assert conflict.status == "failed"
    assert conflict.error_code == "TASK_IDEMPOTENCY_CONFLICT"
    assert len(repository._tasks) == 1


def test_bridge_rejects_snapshot_failure_without_task_side_effect() -> None:
    repository = InMemoryTaskRepository()

    class FailingSnapshot:
        def snapshot(self, call: StructuredAgentCall, profile: AgentTaskProfile):
            raise RuntimeError("raw snapshot detail")

    bridge, _ = _bridge(repository, FailingSnapshot())  # type: ignore[arg-type]

    outcome = bridge.execute(_command())

    assert outcome.status == "failed"
    assert outcome.error_code == "ASYNC_INPUT_SNAPSHOT_FAILED"
    assert "raw snapshot detail" not in (outcome.message or "")
    assert repository._tasks == {}


def test_canonical_snapshot_provider_is_order_independent_and_does_not_expose_input() -> None:
    provider = CanonicalAgentTaskInputSnapshotProvider()
    profile = AgentTaskProfile(
        capability_code="agent.demo.async",
        task_type="agent.demo.async",
        max_attempts=1,
        display_metadata_fields=("call_id",),
    )
    first = provider.snapshot(
        _call(),
        profile,
    )
    reordered = StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.demo.async",
        inputs={
            "executor": "client.executor",
            "owner": "other-user",
            "task_type": "client-controlled-value",
        },
    )

    second = provider.snapshot(reordered, profile)

    assert first.input_fingerprint == second.input_fingerprint
    assert first.display_metadata == {"call_id": "call-1"}
    assert "client-controlled-value" not in first.input_fingerprint


def test_canonical_snapshot_provider_rejects_non_json_input() -> None:
    provider = CanonicalAgentTaskInputSnapshotProvider()
    profile = AgentTaskProfile(
        capability_code="agent.demo.async",
        task_type="agent.demo.async",
        max_attempts=1,
    )
    call = StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.demo.async",
        inputs={"content": object()},
    )

    try:
        provider.snapshot(call, profile)
    except ValueError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("非 JSON 输入必须被拒绝")


def test_router_keeps_unregistered_capability_on_synchronous_strategy() -> None:
    sync = RecordingStrategy(AgentExecutionOutcome.completed({"answer": "sync"}))
    bridge = RecordingStrategy(AgentExecutionOutcome.accepted("unexpected"))
    router = AgentTaskExecutionStrategyRouter(
        AgentTaskProfileRegistry(),
        sync,
        bridge,  # type: ignore[arg-type]
    )

    outcome = router.execute(_command())

    assert outcome.status == "completed"
    assert len(sync.calls) == 1
    assert bridge.calls == []


def test_dispatcher_does_not_bridge_before_policy_authorization() -> None:
    repository = InMemoryTaskRepository()
    snapshot = SnapshotProvider(["fingerprint-1"])
    bridge, registry = _bridge(repository, snapshot)
    sync = RecordingStrategy(AgentExecutionOutcome.completed({"answer": "sync"}))
    router = AgentTaskExecutionStrategyRouter(registry, sync, bridge)

    capability = replace(_capability(), confirmation_policy="always")
    catalog = _Catalog(capability)
    dispatcher = AgentCallDispatcher(
        catalog,
        AgentCallPolicyValidator(catalog),
        execution_strategy=router,
    )

    result = dispatcher.dispatch(
        AgentCallDispatchCommand(call=_call(), principal=_principal())
    )

    assert result.status == "confirmation_required"
    assert snapshot.calls == []
    assert repository._tasks == {}


def test_dispatcher_returns_accepted_after_policy_authorization() -> None:
    repository = InMemoryTaskRepository()
    snapshot = SnapshotProvider(["fingerprint-1"])
    bridge, registry = _bridge(repository, snapshot)
    sync = RecordingStrategy(AgentExecutionOutcome.completed({"answer": "sync"}))
    router = AgentTaskExecutionStrategyRouter(registry, sync, bridge)
    catalog = _Catalog(_capability())
    dispatcher = AgentCallDispatcher(
        catalog,
        AgentCallPolicyValidator(catalog),
        execution_strategy=router,
    )

    result = dispatcher.dispatch(
        AgentCallDispatchCommand(call=_call(), principal=_principal())
    )

    assert result.status == "accepted"
    assert result.execution_reference is not None
    assert result.result is None


@dataclass
class _Catalog:
    capability: PlatformCapability

    def get_available(
        self,
        code: str,
        *,
        permissions: Iterable[str] = (),
    ) -> PlatformCapability | None:
        return self.capability if code == self.capability.code else None
