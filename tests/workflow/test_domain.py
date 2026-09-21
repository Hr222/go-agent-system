from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.platform.workflow.domain import (
    WorkflowEdgeDefinition,
    WorkflowEventType,
    WorkflowNodeDefinition,
    WorkflowNodeStatus,
    WorkflowNodeType,
    WorkflowRunStatus,
    WorkflowStateError,
    WorkflowValidationError,
    WorkflowVersion,
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _version(*, max_attempts: int = 1) -> WorkflowVersion:
    return WorkflowVersion(
        workflow_code="tender-flow",
        version="v1",
        nodes=(
            WorkflowNodeDefinition(
                node_id="prepare",
                node_type=WorkflowNodeType.CAPABILITY,
                capability_code="tender.prepare",
                output_fields=("document_id",),
                max_attempts=max_attempts,
            ),
            WorkflowNodeDefinition(
                node_id="generate",
                node_type=WorkflowNodeType.CAPABILITY,
                capability_code="tender.generate",
                input_fields=("document_id",),
                output_fields=("artifact_id",),
            ),
        ),
        edges=(
            WorkflowEdgeDefinition(
                source_node_id="prepare",
                target_node_id="generate",
                output_fields=("document_id",),
            ),
        ),
    )


def test_version_rejects_invalid_graph_and_remains_immutable() -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowVersion(
            workflow_code="flow",
            version="v1",
            nodes=(
                WorkflowNodeDefinition("step", WorkflowNodeType.CAPABILITY, "capability.one"),
                WorkflowNodeDefinition("step", WorkflowNodeType.CAPABILITY, "capability.two"),
            ),
        )

    with pytest.raises(WorkflowValidationError):
        WorkflowVersion(
            workflow_code="flow",
            version="v1",
            nodes=(WorkflowNodeDefinition("step", WorkflowNodeType.CAPABILITY, "capability.one"),),
            edges=(WorkflowEdgeDefinition("step", "missing"),),
        )

    nodes = (
        WorkflowNodeDefinition("first", WorkflowNodeType.CAPABILITY, "capability.one"),
        WorkflowNodeDefinition("second", WorkflowNodeType.CAPABILITY, "capability.two"),
    )
    with pytest.raises(WorkflowValidationError):
        WorkflowVersion(
            workflow_code="flow",
            version="v1",
            nodes=nodes,
            edges=(
                WorkflowEdgeDefinition("first", "second"),
                WorkflowEdgeDefinition("second", "first"),
            ),
        )

    version = _version()
    assert isinstance(version.nodes, tuple)
    assert isinstance(version.edges, tuple)
    with pytest.raises(FrozenInstanceError):
        version.enabled = False  # type: ignore[misc]


def test_version_rejects_edge_output_not_declared_by_target() -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowVersion(
            workflow_code="flow",
            version="v1",
            nodes=(
                WorkflowNodeDefinition(
                    "first",
                    WorkflowNodeType.CAPABILITY,
                    "capability.one",
                    output_fields=("artifact_id",),
                ),
                WorkflowNodeDefinition("second", WorkflowNodeType.CAPABILITY, "capability.two"),
            ),
            edges=(WorkflowEdgeDefinition("first", "second", ("artifact_id",)),),
        )


def test_run_tracks_dependency_readiness_and_success() -> None:
    version = _version()
    run = run = __import__(
        "app.platform.workflow.domain", fromlist=["WorkflowRun"]
    ).WorkflowRun.create(
        version=version,
        owner_subject="user-1",
        idempotency_key="run-1",
        input_fingerprint="sha256:input",
        now=NOW,
    )

    assert run.status is WorkflowRunStatus.QUEUED
    assert run.ready_nodes(version) == ("prepare",)
    assert run.events[0].event_type is WorkflowEventType.RUN_CREATED
    assert run.events[0].run_id == run.id

    run.start_node(version=version, node_id="prepare", now=NOW, command_id="start-prepare")
    with pytest.raises(WorkflowStateError):
        run.start_node(version=version, node_id="generate", now=NOW, command_id="start-generate")

    run.succeed_node(
        version=version,
        node_id="prepare",
        result_summary="准备完成",
        output_fingerprint="sha256:output",
        now=NOW,
        command_id="succeed-prepare",
    )
    assert run.ready_nodes(version) == ("generate",)

    run.start_node(version=version, node_id="generate", now=NOW, command_id="start-generate")
    run.accept_node(
        node_id="generate",
        execution_reference="exec:tender:opaque-1",
        now=NOW,
        command_id="accept-generate",
    )
    assert run.status is WorkflowRunStatus.ACCEPTED
    run.succeed_node(
        version=version,
        node_id="generate",
        result_summary="生成完成",
        output_fingerprint="sha256:artifact",
        now=NOW,
        command_id="succeed-generate",
    )
    assert run.status is WorkflowRunStatus.SUCCEEDED

    event_count = len(run.events)
    run.succeed_node(
        version=version,
        node_id="generate",
        result_summary="生成完成",
        output_fingerprint="sha256:artifact",
        now=NOW,
        command_id="succeed-generate",
    )
    assert len(run.events) == event_count


def test_retryable_failure_requeues_and_permanent_failure_fails_run() -> None:
    version = _version(max_attempts=2)
    run = __import__("app.platform.workflow.domain", fromlist=["WorkflowRun"]).WorkflowRun.create(
        version=version,
        owner_subject="user-1",
        idempotency_key="run-retry",
        input_fingerprint="sha256:input",
        now=NOW,
    )
    run.start_node(version=version, node_id="prepare", now=NOW, command_id="start-1")
    run.fail_node(
        version=version,
        node_id="prepare",
        error_code="UPSTREAM_TIMEOUT",
        retryable=True,
        now=NOW,
        command_id="fail-1",
    )
    assert run.node("prepare").status is WorkflowNodeStatus.QUEUED
    assert run.node("prepare").attempt_count == 1
    assert run.ready_nodes(version) == ("prepare",)

    run.start_node(version=version, node_id="prepare", now=NOW, command_id="start-2")
    run.fail_node(
        version=version,
        node_id="prepare",
        error_code="DOCUMENT_INVALID",
        retryable=True,
        now=NOW,
        command_id="fail-2",
    )
    assert run.node("prepare").status is WorkflowNodeStatus.FAILED
    assert run.status is WorkflowRunStatus.FAILED


def test_cancel_running_run_waits_for_executor_confirmation_and_replays_idempotently() -> None:
    version = _version()
    run = __import__("app.platform.workflow.domain", fromlist=["WorkflowRun"]).WorkflowRun.create(
        version=version,
        owner_subject="user-1",
        idempotency_key="run-cancel",
        input_fingerprint="sha256:input",
        now=NOW,
    )
    run.start_node(version=version, node_id="prepare", now=NOW, command_id="start")
    run.request_cancel(now=NOW, command_id="cancel")
    event_count = len(run.events)

    run.request_cancel(now=NOW, command_id="cancel")
    assert len(run.events) == event_count
    assert run.status is WorkflowRunStatus.CANCEL_REQUESTED
    assert run.node("prepare").status is WorkflowNodeStatus.CANCEL_REQUESTED

    run.confirm_node_cancel(node_id="prepare", now=NOW, command_id="confirm")
    assert run.status is WorkflowRunStatus.CANCELLED
    event_count = len(run.events)
    run.confirm_node_cancel(node_id="prepare", now=NOW, command_id="confirm")
    assert len(run.events) == event_count


def test_skipped_node_can_complete_run_without_execution_attempt() -> None:
    version = WorkflowVersion(
        workflow_code="single",
        version="v1",
        nodes=(WorkflowNodeDefinition("step", WorkflowNodeType.CAPABILITY, "capability.one"),),
    )
    from app.platform.workflow.domain import WorkflowRun

    run = WorkflowRun.create(
        version=version,
        owner_subject="user-1",
        idempotency_key="skip-1",
        input_fingerprint="sha256:input",
        now=NOW,
    )
    run.skip_node(version=version, node_id="step", reason="条件不满足", now=NOW, command_id="skip")

    assert run.node("step").status is WorkflowNodeStatus.SKIPPED
    assert run.status is WorkflowRunStatus.SUCCEEDED
