from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from uuid import UUID

from app.platform.security.domain import RequestPrincipal
from app.platform.workflow.domain import (
    WorkflowIdempotencyConflictError,
    WorkflowNodeStatus,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStateError,
    WorkflowValidationError,
)
from app.platform.workflow.ports import (
    WorkflowCommandReceipt,
    WorkflowDefinitionRegistryPort,
    WorkflowNodeExecutionCommand,
    WorkflowNodeExecutionOutcome,
    WorkflowNodeExecutorPort,
    WorkflowRepositoryPort,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CreateWorkflowRunCommand:
    principal: RequestPrincipal
    workflow_code: str
    workflow_version: str
    idempotency_key: str
    inputs: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class WorkflowNodeView:
    node_id: str
    capability_code: str
    status: WorkflowNodeStatus
    attempt_count: int
    execution_reference: str | None
    result_summary: str | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class WorkflowRunView:
    id: UUID
    workflow_code: str
    workflow_version: str
    owner_subject: str
    status: WorkflowRunStatus
    nodes: tuple[WorkflowNodeView, ...]
    result_summary: str | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_run(cls, run: WorkflowRun) -> "WorkflowRunView":
        return cls(
            id=run.id,
            workflow_code=run.workflow_code,
            workflow_version=run.workflow_version,
            owner_subject=run.owner_subject,
            status=run.status,
            nodes=tuple(
                WorkflowNodeView(
                    node_id=node.node_id,
                    capability_code=node.capability_code,
                    status=node.status,
                    attempt_count=node.attempt_count,
                    execution_reference=node.execution_reference,
                    result_summary=node.result_summary,
                    failure_code=node.failure_code,
                )
                for node in run.nodes
            ),
            result_summary=run.result_summary,
            failure_code=run.failure_code,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class WorkflowApplication:
    """Workflow 生命周期的受信任 Application 边界。"""

    def __init__(
        self,
        repository: WorkflowRepositoryPort,
        registry: WorkflowDefinitionRegistryPort,
        *,
        clock=_utc_now,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._clock = clock

    def create_run(self, command: CreateWorkflowRunCommand) -> WorkflowRunView:
        principal = self._require_principal(command.principal)
        version = self._registry.get(command.workflow_code, command.workflow_version)
        if version is None or not version.enabled:
            raise WorkflowValidationError("Workflow Version 不可用。")
        self._registry.validate_access(version, principal.permissions)
        root_fields = tuple(
            field
            for node in version.nodes
            if not version.predecessors(node.node_id)
            for field in node.input_fields
        )
        normalized_inputs = self._validate_inputs(root_fields, command.inputs)
        run = WorkflowRun.create(
            version=version,
            owner_subject=principal.subject.strip(),
            idempotency_key=command.idempotency_key,
            input_fingerprint=_fingerprint(normalized_inputs),
            now=self._clock(),
        )
        existing = self._repository.create_or_get(run)
        if existing.input_fingerprint != run.input_fingerprint:
            raise WorkflowIdempotencyConflictError("同一幂等键使用了不同的输入指纹。")
        return WorkflowRunView.from_run(existing)

    def get_owned(self, *, principal: RequestPrincipal, run_id: UUID) -> WorkflowRunView:
        subject = self._require_principal(principal).subject.strip()
        run = self._repository.get_owned(run_id=run_id, owner_subject=subject)
        if run is None:
            raise LookupError("Workflow 不可用。")
        return WorkflowRunView.from_run(run)

    def execute_node(
        self,
        *,
        principal: RequestPrincipal,
        run_id: UUID,
        node_id: str,
        inputs: Mapping[str, object],
        executor: WorkflowNodeExecutorPort,
        command_id: str,
    ) -> WorkflowRunView:
        trusted = self._require_principal(principal)
        run = self._repository.get_for_update(run_id)
        if run is None or run.owner_subject != trusted.subject.strip():
            raise LookupError("Workflow 不可用。")
        if self._repository.has_processed_command(
            run_id=run_id, command_type="execute-node", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        version = self._registry.get(run.workflow_code, run.workflow_version)
        if version is None:
            raise WorkflowValidationError("Workflow Version 不可用。")
        if node_id not in run.ready_nodes(version):
            raise WorkflowStateError("节点前置依赖尚未满足。")
        node_definition = version.node(node_id)
        normalized_inputs = self._validate_inputs(node_definition.input_fields, inputs)
        run.start_node(version=version, node_id=node_id, now=self._clock(), command_id=command_id)
        self._repository.save(run)
        try:
            outcome = executor.execute(
                WorkflowNodeExecutionCommand(
                    principal=trusted,
                    version=version,
                    node=node_definition,
                    inputs=normalized_inputs,
                )
            )
        except Exception:  # noqa: BLE001 - executor boundary must not leak provider details
            outcome = WorkflowNodeExecutionOutcome.failed(
                error_code="EXECUTOR_UNAVAILABLE",
                message="Workflow 节点执行器暂时不可用。",
                retryable=True,
            )
        now = self._clock()
        if outcome.status == "completed":
            run.succeed_node(
                version=version,
                node_id=node_id,
                result_summary=outcome.result_summary or "节点已完成。",
                output_fingerprint=outcome.output_fingerprint,
                now=now,
                command_id=command_id,
            )
        elif outcome.status == "accepted":
            run.accept_node(
                node_id=node_id,
                execution_reference=outcome.execution_reference or "",
                now=now,
                command_id=command_id,
            )
        else:
            run.fail_node(
                version=version,
                node_id=node_id,
                error_code=outcome.error_code or "WORKFLOW_EXECUTION_FAILED",
                retryable=outcome.retryable,
                now=now,
                command_id=command_id,
            )
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "execute-node", command_id),
        )
        return WorkflowRunView.from_run(run)

    def complete_node(
        self,
        *,
        principal: RequestPrincipal,
        run_id: UUID,
        node_id: str,
        result_summary: str,
        output_fingerprint: str | None,
        command_id: str,
    ) -> WorkflowRunView:
        run, version = self._owned_run(principal, run_id)
        if self._repository.has_processed_command(
            run_id=run_id, command_type="complete-node", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        run.succeed_node(
            version=version,
            node_id=node_id,
            result_summary=result_summary,
            output_fingerprint=output_fingerprint,
            now=self._clock(),
            command_id=command_id,
        )
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "complete-node", command_id),
        )
        return WorkflowRunView.from_run(run)

    def fail_node(
        self,
        *,
        principal: RequestPrincipal,
        run_id: UUID,
        node_id: str,
        error_code: str,
        retryable: bool,
        command_id: str,
    ) -> WorkflowRunView:
        run, version = self._owned_run(principal, run_id)
        if self._repository.has_processed_command(
            run_id=run_id, command_type="fail-node", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        run.fail_node(
            version=version,
            node_id=node_id,
            error_code=error_code,
            retryable=retryable,
            now=self._clock(),
            command_id=command_id,
        )
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "fail-node", command_id),
        )
        return WorkflowRunView.from_run(run)

    def skip_node(
        self,
        *,
        principal: RequestPrincipal,
        run_id: UUID,
        node_id: str,
        reason: str,
        command_id: str,
    ) -> WorkflowRunView:
        run, version = self._owned_run(principal, run_id)
        if self._repository.has_processed_command(
            run_id=run_id, command_type="skip-node", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        run.skip_node(
            version=version,
            node_id=node_id,
            reason=reason,
            now=self._clock(),
            command_id=command_id,
        )
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "skip-node", command_id),
        )
        return WorkflowRunView.from_run(run)

    def confirm_node_cancel(
        self,
        *,
        principal: RequestPrincipal,
        run_id: UUID,
        node_id: str,
        command_id: str,
    ) -> WorkflowRunView:
        run, _ = self._owned_run(principal, run_id)
        if self._repository.has_processed_command(
            run_id=run_id, command_type="confirm-cancel", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        run.confirm_node_cancel(node_id=node_id, now=self._clock(), command_id=command_id)
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "confirm-cancel", command_id),
        )
        return WorkflowRunView.from_run(run)

    def cancel(
        self, *, principal: RequestPrincipal, run_id: UUID, command_id: str
    ) -> WorkflowRunView:
        subject = self._require_principal(principal).subject.strip()
        run = self._repository.get_for_update(run_id)
        if run is None or run.owner_subject != subject:
            raise LookupError("Workflow 不可用。")
        if self._repository.has_processed_command(
            run_id=run_id, command_type="cancel", command_id=command_id
        ):
            return WorkflowRunView.from_run(run)
        run.request_cancel(now=self._clock(), command_id=command_id)
        self._repository.save(
            run,
            command_receipt=WorkflowCommandReceipt(run_id, "cancel", command_id),
        )
        return WorkflowRunView.from_run(run)

    def _owned_run(self, principal: RequestPrincipal, run_id: UUID) -> tuple[WorkflowRun, object]:
        trusted = self._require_principal(principal)
        run = self._repository.get_for_update(run_id)
        if run is None or run.owner_subject != trusted.subject.strip():
            raise LookupError("Workflow 不可用。")
        version = self._registry.get(run.workflow_code, run.workflow_version)
        if version is None:
            raise WorkflowValidationError("Workflow Version 不可用。")
        return run, version

    @staticmethod
    def _require_principal(principal: RequestPrincipal) -> RequestPrincipal:
        if (
            not isinstance(principal, RequestPrincipal)
            or not principal.authenticated
            or not isinstance(principal.subject, str)
            or not principal.subject.strip()
        ):
            raise PermissionError("Workflow 需要已认证主体。")
        return principal

    @staticmethod
    def _validate_inputs(fields, inputs: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(inputs, Mapping):
            raise WorkflowValidationError("Workflow 输入必须是 JSON 对象。")
        normalized = dict(inputs)
        fields = tuple(fields)
        if set(fields) - set(normalized):
            raise WorkflowValidationError("Workflow 输入缺少必需字段。")
        if set(normalized) - set(fields):
            raise WorkflowValidationError("Workflow 输入包含未声明字段。")
        try:
            json.dumps(normalized, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise WorkflowValidationError("Workflow 输入必须是有限的 JSON 对象。") from exc
        return normalized


def _fingerprint(value: Mapping[str, object]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["CreateWorkflowRunCommand", "WorkflowApplication", "WorkflowRunView"]
