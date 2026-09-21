from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.security.domain import RequestPrincipal
from app.platform.workflow.application import (
    CreateWorkflowRunCommand,
    WorkflowApplication,
    WorkflowDefinitionRegistry,
)
from app.platform.workflow.domain import (
    WorkflowEdgeDefinition,
    WorkflowNodeDefinition,
    WorkflowNodeType,
    WorkflowVersion,
)
from app.platform.workflow.ports import (
    WorkflowNodeExecutionCommand,
    WorkflowNodeExecutionOutcome,
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


class Catalog:
    def __init__(self, capabilities: tuple[PlatformCapability, ...]) -> None:
        self.capabilities = {item.code: item for item in capabilities}

    def get_available(self, code: str, *, permissions=()):
        capability = self.capabilities.get(code)
        if capability is None or not capability.enabled:
            return None
        return capability if set(capability.permission).issubset(set(permissions)) else None


class Repository:
    def __init__(self) -> None:
        self.runs = {}
        self.submissions = {}
        self.receipts = set()

    def get(self, run_id: UUID):
        return self.runs.get(run_id)

    def get_for_update(self, run_id: UUID):
        return self.get(run_id)

    def get_owned(self, *, run_id: UUID, owner_subject: str):
        run = self.get(run_id)
        return run if run is not None and run.owner_subject == owner_subject else None

    def create_or_get(self, run):
        key = (run.owner_subject, run.workflow_code, run.workflow_version, run.idempotency_key)
        existing_id = self.submissions.get(key)
        if existing_id is not None:
            return self.runs[existing_id]
        self.runs[run.id] = run
        self.submissions[key] = run.id
        return run

    def save(self, run, *, command_receipt=None):
        self.runs[run.id] = run
        if command_receipt is not None:
            self.receipts.add(
                (command_receipt.run_id, command_receipt.command_type, command_receipt.command_id)
            )

    def has_processed_command(self, *, run_id, command_type, command_id):
        return (run_id, command_type, command_id) in self.receipts


class Executor:
    def __init__(self, outcome):
        self.outcome = outcome
        self.commands: list[WorkflowNodeExecutionCommand] = []

    def execute(self, command: WorkflowNodeExecutionCommand):
        self.commands.append(command)
        return self.outcome


def _capability(
    *, code: str = "tender.generate_bid_skeleton", required_fields=("source_document",)
) -> PlatformCapability:
    return PlatformCapability(
        code=code,
        capability_type="agent",
        description="Tender",
        input_schema={
            "type": "object",
            "properties": {
                "source_document": {"type": "string"},
                "artifact_id": {"type": "string"},
            },
        },
        output_schema={"type": "object", "properties": {"artifact_id": {"type": "string"}}},
        required_fields=required_fields,
        confirmation_policy="always",
        permission=("agent:tender:execute",),
        enabled=True,
        timeout_seconds=60,
        error_boundary="tender-v1",
        dispatch_key=code.replace("tender.", "agent.tender."),
        retrieval_metadata={},
    )


def _app() -> tuple[WorkflowApplication, Repository, RequestPrincipal]:
    version = WorkflowVersion(
        workflow_code="tender-flow",
        version="v1",
        nodes=(
            WorkflowNodeDefinition(
                "generate",
                WorkflowNodeType.CAPABILITY,
                "tender.generate_bid_skeleton",
                input_fields=("source_document",),
                output_fields=("artifact_id",),
            ),
        ),
        edges=(),
    )
    catalog = Catalog((_capability(),))
    registry = WorkflowDefinitionRegistry(
        (version,), catalog, validation_permissions=("agent:tender:execute",)
    )
    repository = Repository()
    principal = RequestPrincipal(
        subject="user-1",
        permissions=frozenset({"agent:tender:execute"}),
        authenticated=True,
    )
    return WorkflowApplication(repository, registry, clock=lambda: NOW), repository, principal


def test_create_is_idempotent_and_does_not_store_raw_input() -> None:
    application, repository, principal = _app()
    command = CreateWorkflowRunCommand(
        principal=principal,
        workflow_code="tender-flow",
        workflow_version="v1",
        idempotency_key="create-1",
        inputs={"source_document": "attachment:opaque"},
    )
    first = application.create_run(command)
    replay = application.create_run(command)

    assert first.id == replay.id
    assert len(repository.runs[first.id].events) == 1
    assert repository.runs[first.id].input_fingerprint


def test_execute_node_requires_permission_and_supports_accepted() -> None:
    application, repository, principal = _app()
    run = application.create_run(
        CreateWorkflowRunCommand(
            principal=principal,
            workflow_code="tender-flow",
            workflow_version="v1",
            idempotency_key="create-accepted",
            inputs={"source_document": "attachment:opaque"},
        )
    )
    executor = Executor(WorkflowNodeExecutionOutcome.accepted("task:opaque-1"))
    accepted = application.execute_node(
        principal=principal,
        run_id=run.id,
        node_id="generate",
        inputs={"source_document": "attachment:opaque"},
        executor=executor,
        command_id="execute-1",
    )

    assert accepted.nodes[0].execution_reference == "task:opaque-1"
    assert accepted.nodes[0].status.value == "accepted"
    assert len(executor.commands) == 1
    assert repository.runs[run.id].input_fingerprint

    completed = application.complete_node(
        principal=principal,
        run_id=run.id,
        node_id="generate",
        result_summary="已完成",
        output_fingerprint="sha256:artifact",
        command_id="complete-1",
    )
    replay = application.complete_node(
        principal=principal,
        run_id=run.id,
        node_id="generate",
        result_summary="已完成",
        output_fingerprint="sha256:artifact",
        command_id="complete-1",
    )
    assert completed.status.value == "succeeded"
    assert replay.id == completed.id
    assert len(repository.runs[run.id].events) == 7

    with pytest.raises(LookupError):
        application.get_owned(
            principal=RequestPrincipal(subject="other", authenticated=True),
            run_id=run.id,
        )


def test_dependency_prevents_execution_until_predecessor_succeeds() -> None:
    first_cap = _capability(required_fields=())
    second_cap = _capability(code="tender.generate_followup", required_fields=("artifact_id",))
    catalog = Catalog((first_cap, second_cap))
    version = WorkflowVersion(
        workflow_code="chain",
        version="v1",
        nodes=(
            WorkflowNodeDefinition(
                "first",
                WorkflowNodeType.CAPABILITY,
                    first_cap.code,
                output_fields=("artifact_id",),
            ),
            WorkflowNodeDefinition(
                "second",
                WorkflowNodeType.CAPABILITY,
                    second_cap.code,
                input_fields=("artifact_id",),
            ),
        ),
        edges=(WorkflowEdgeDefinition("first", "second", ("artifact_id",)),),
    )
    registry = WorkflowDefinitionRegistry(
        (version,), catalog, validation_permissions=("agent:tender:execute",)
    )
    repository = Repository()
    principal = RequestPrincipal(
        subject="user-1", permissions=frozenset({"agent:tender:execute"}), authenticated=True
    )
    application = WorkflowApplication(repository, registry, clock=lambda: NOW)
    run = application.create_run(CreateWorkflowRunCommand(principal, "chain", "v1", "chain-1", {}))
    with pytest.raises(Exception, match="前置依赖"):
        application.execute_node(
            principal=principal,
            run_id=run.id,
            node_id="second",
            inputs={"artifact_id": "x"},
            executor=Executor(WorkflowNodeExecutionOutcome.completed("done")),
            command_id="execute-second",
        )
