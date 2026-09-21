"""Workflow Definition、Run 与 Node Run 的纯领域模型。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping
from uuid import UUID, uuid4


class WorkflowValidationError(ValueError):
    """Workflow Definition 或运行事实不满足领域约束。"""


class WorkflowStateError(RuntimeError):
    """Workflow 状态不能执行请求的转换。"""


class WorkflowIdempotencyConflictError(ValueError):
    """同一 Workflow 幂等键使用了不同输入。"""


class WorkflowNodeType(StrEnum):
    CAPABILITY = "capability"


class WorkflowRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    ACCEPTED = "accepted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class WorkflowNodeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    ACCEPTED = "accepted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class WorkflowEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_STARTED = "RUN_STARTED"
    RUN_ACCEPTED = "RUN_ACCEPTED"
    RUN_SUCCEEDED = "RUN_SUCCEEDED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCEL_REQUESTED = "RUN_CANCEL_REQUESTED"
    RUN_CANCELLED = "RUN_CANCELLED"
    NODE_STARTED = "NODE_STARTED"
    NODE_ACCEPTED = "NODE_ACCEPTED"
    NODE_SUCCEEDED = "NODE_SUCCEEDED"
    NODE_FAILED = "NODE_FAILED"
    NODE_RETRY_SCHEDULED = "NODE_RETRY_SCHEDULED"
    NODE_SKIPPED = "NODE_SKIPPED"
    NODE_CANCEL_REQUESTED = "NODE_CANCEL_REQUESTED"
    NODE_CANCELLED = "NODE_CANCELLED"


_EVENT_METADATA_FIELDS: dict[WorkflowEventType, frozenset[str]] = {
    WorkflowEventType.RUN_CREATED: frozenset({"workflow_code", "workflow_version"}),
    WorkflowEventType.RUN_STARTED: frozenset(),
    WorkflowEventType.RUN_ACCEPTED: frozenset({"node_id"}),
    WorkflowEventType.RUN_SUCCEEDED: frozenset(),
    WorkflowEventType.RUN_FAILED: frozenset({"node_id", "error_code"}),
    WorkflowEventType.RUN_CANCEL_REQUESTED: frozenset(),
    WorkflowEventType.RUN_CANCELLED: frozenset(),
    WorkflowEventType.NODE_STARTED: frozenset({"node_id", "attempt_number"}),
    WorkflowEventType.NODE_ACCEPTED: frozenset(
        {"node_id", "attempt_number", "execution_reference"}
    ),
    WorkflowEventType.NODE_SUCCEEDED: frozenset({"node_id", "attempt_number"}),
    WorkflowEventType.NODE_FAILED: frozenset({"node_id", "attempt_number", "error_code"}),
    WorkflowEventType.NODE_RETRY_SCHEDULED: frozenset({"node_id", "attempt_number", "error_code"}),
    WorkflowEventType.NODE_SKIPPED: frozenset({"node_id", "skip_reason"}),
    WorkflowEventType.NODE_CANCEL_REQUESTED: frozenset({"node_id", "attempt_number"}),
    WorkflowEventType.NODE_CANCELLED: frozenset({"node_id", "attempt_number", "cancel_mode"}),
}


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SAFE_ERROR = re.compile(r"^[A-Z][A-Z0-9_.-]{1,63}$")
_SAFE_FINGERPRINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowValidationError(f"{label}不能为空。")
    return value.strip()


def _identifier(value: str, label: str) -> str:
    normalized = _text(value, label)
    if not _IDENTIFIER.fullmatch(normalized):
        raise WorkflowValidationError(f"{label}格式无效。")
    return normalized


def _opaque_reference(value: str, label: str) -> str:
    normalized = _text(value, label)
    if _SAFE_REFERENCE.fullmatch(normalized) is None:
        raise WorkflowValidationError(f"{label}必须是不透明的安全引用。")
    return normalized


def _fingerprint(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    normalized = _text(value, label)
    if _SAFE_FINGERPRINT.fullmatch(normalized) is None:
        raise WorkflowValidationError(f"{label}格式无效。")
    return normalized


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise WorkflowValidationError(f"{label}必须包含时区。")
    return value


def _json_object(value: Mapping[str, object], label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise WorkflowValidationError(f"{label}必须是 JSON 对象。")
    normalized = dict(value)
    try:
        json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(f"{label}必须是有限的 JSON 对象。") from exc
    return normalized


@dataclass(frozen=True, slots=True)
class WorkflowNodeDefinition:
    node_id: str
    node_type: WorkflowNodeType
    capability_code: str
    max_attempts: int = 1
    input_fields: tuple[str, ...] = ()
    output_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _identifier(self.node_id, "节点标识"))
        object.__setattr__(
            self,
            "capability_code",
            _identifier(self.capability_code, "能力代码"),
        )
        try:
            node_type = WorkflowNodeType(self.node_type)
        except ValueError as exc:
            raise WorkflowValidationError("节点类型无效。") from exc
        object.__setattr__(self, "node_type", node_type)
        if node_type is not WorkflowNodeType.CAPABILITY:
            raise WorkflowValidationError("当前只支持 capability 节点。")
        if isinstance(self.max_attempts, bool) or self.max_attempts <= 0:
            raise WorkflowValidationError("节点最大尝试次数必须为正整数。")
        for label, fields in (("输入字段", self.input_fields), ("输出字段", self.output_fields)):
            normalized_fields = tuple(_identifier(field, f"{label}名") for field in fields)
            if len(set(normalized_fields)) != len(normalized_fields):
                raise WorkflowValidationError(f"{label}必须是非重复的非空字段名。")
            object.__setattr__(
                self, "input_fields" if label == "输入字段" else "output_fields", normalized_fields
            )


@dataclass(frozen=True, slots=True)
class WorkflowEdgeDefinition:
    source_node_id: str
    target_node_id: str
    output_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_node_id", _identifier(self.source_node_id, "边源节点"))
        object.__setattr__(self, "target_node_id", _identifier(self.target_node_id, "边目标节点"))
        if self.source_node_id == self.target_node_id:
            raise WorkflowValidationError("Workflow 不允许节点自环。")
        normalized_fields = tuple(
            _identifier(field, "边输出字段名") for field in self.output_fields
        )
        if len(set(normalized_fields)) != len(normalized_fields):
            raise WorkflowValidationError("边输出字段不能重复。")
        object.__setattr__(self, "output_fields", normalized_fields)


@dataclass(frozen=True, slots=True)
class WorkflowVersion:
    workflow_code: str
    version: str
    nodes: tuple[WorkflowNodeDefinition, ...]
    edges: tuple[WorkflowEdgeDefinition, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "workflow_code", _identifier(self.workflow_code, "Workflow 代码"))
        object.__setattr__(self, "version", _identifier(self.version, "Workflow 版本"))
        if not self.nodes:
            raise WorkflowValidationError("Workflow Version 至少需要一个节点。")
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise WorkflowValidationError("Workflow 节点标识不能重复。")
        node_set = set(node_ids)
        for edge in self.edges:
            if edge.source_node_id not in node_set or edge.target_node_id not in node_set:
                raise WorkflowValidationError("Workflow 边必须引用当前 Version 的节点。")
            source = next(node for node in self.nodes if node.node_id == edge.source_node_id)
            target = next(node for node in self.nodes if node.node_id == edge.target_node_id)
            if not set(edge.output_fields).issubset(source.output_fields):
                raise WorkflowValidationError("边引用了源节点未声明的输出字段。")
            if not set(edge.output_fields).issubset(target.input_fields):
                raise WorkflowValidationError("边输出字段未被目标节点声明为输入字段。")
        _assert_acyclic(node_ids, self.edges)

    @property
    def key(self) -> str:
        return f"{self.workflow_code}:{self.version}"

    def node(self, node_id: str) -> WorkflowNodeDefinition:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise WorkflowValidationError("Workflow 节点不存在。")

    def predecessors(self, node_id: str) -> tuple[str, ...]:
        self.node(node_id)
        return tuple(edge.source_node_id for edge in self.edges if edge.target_node_id == node_id)


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    run_id: UUID
    sequence: int
    transition_id: str
    event_type: WorkflowEventType
    metadata: Mapping[str, object]
    created_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, UUID):
            raise WorkflowValidationError("Run 标识无效。")
        if self.sequence <= 0:
            raise WorkflowValidationError("事件序号必须为正整数。")
        _text(self.transition_id, "转换标识")
        try:
            event_type = WorkflowEventType(self.event_type)
        except ValueError as exc:
            raise WorkflowValidationError("Workflow 事件类型无效。") from exc
        object.__setattr__(self, "event_type", event_type)
        normalized = _json_object(self.metadata, "事件元数据")
        allowed = _EVENT_METADATA_FIELDS[event_type]
        if set(normalized) - allowed:
            raise WorkflowValidationError("事件元数据包含未允许的字段。")
        if "node_id" in normalized:
            _identifier(normalized["node_id"], "事件节点标识")
        if "attempt_number" in normalized and (
            isinstance(normalized["attempt_number"], bool)
            or not isinstance(normalized["attempt_number"], int)
            or normalized["attempt_number"] <= 0
        ):
            raise WorkflowValidationError("事件尝试序号无效。")
        if "error_code" in normalized and (
            not isinstance(normalized["error_code"], str)
            or _SAFE_ERROR.fullmatch(normalized["error_code"]) is None
        ):
            raise WorkflowValidationError("事件错误码无效。")
        if "execution_reference" in normalized:
            _opaque_reference(normalized["execution_reference"], "事件执行引用")
        if "cancel_mode" in normalized and normalized["cancel_mode"] not in {
            "queued",
            "confirmed",
        }:
            raise WorkflowValidationError("事件取消模式无效。")
        object.__setattr__(self, "metadata", normalized)
        _utc(self.created_at, "事件时间")


@dataclass(slots=True)
class WorkflowNodeRun:
    node_id: str
    node_type: WorkflowNodeType
    capability_code: str
    max_attempts: int
    status: WorkflowNodeStatus = WorkflowNodeStatus.QUEUED
    attempt_count: int = 0
    execution_reference: str | None = None
    result_summary: str | None = None
    output_fingerprint: str | None = None
    failure_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.node_id = _identifier(self.node_id, "节点标识")
        self.capability_code = _identifier(self.capability_code, "能力代码")
        try:
            self.node_type = WorkflowNodeType(self.node_type)
        except ValueError as exc:
            raise WorkflowValidationError("节点类型无效。") from exc
        if self.node_type is not WorkflowNodeType.CAPABILITY:
            raise WorkflowValidationError("节点类型无效。")
        if isinstance(self.max_attempts, bool) or self.max_attempts <= 0:
            raise WorkflowValidationError("节点最大尝试次数必须为正整数。")
        if self.attempt_count < 0 or self.attempt_count > self.max_attempts:
            raise WorkflowValidationError("节点尝试次数超出范围。")
        if self.execution_reference is not None:
            self.execution_reference = _opaque_reference(self.execution_reference, "执行引用")
        self.output_fingerprint = _fingerprint(self.output_fingerprint, "输出指纹")
        if self.failure_code is not None and _SAFE_ERROR.fullmatch(self.failure_code) is None:
            raise WorkflowValidationError("错误码格式无效。")

    def start(
        self, *, now: datetime, transition_id: str, run_id: UUID | None = None
    ) -> WorkflowEvent:
        if self.status is not WorkflowNodeStatus.QUEUED:
            raise WorkflowStateError("只有 queued 节点可以开始执行。")
        if self.attempt_count >= self.max_attempts:
            raise WorkflowStateError("节点已耗尽最大尝试次数。")
        self.attempt_count += 1
        self.status = WorkflowNodeStatus.RUNNING
        self.updated_at = _utc(now, "节点开始时间")
        return _node_event(
            self,
            WorkflowEventType.NODE_STARTED,
            transition_id,
            now,
            {"attempt_number": self.attempt_count},
            run_id=run_id,
        )

    def accept(
        self,
        *,
        execution_reference: str,
        now: datetime,
        transition_id: str,
        run_id: UUID | None = None,
    ) -> WorkflowEvent:
        if self.status is WorkflowNodeStatus.ACCEPTED:
            if self.execution_reference != _opaque_reference(execution_reference, "执行引用"):
                raise WorkflowIdempotencyConflictError("同一节点接收使用了不同的执行引用。")
            return _node_event(
                self,
                WorkflowEventType.NODE_ACCEPTED,
                transition_id,
                now,
                {
                    "attempt_number": self.attempt_count,
                    "execution_reference": self.execution_reference,
                },
                run_id=run_id,
            )
        self._require_active()
        self.execution_reference = _opaque_reference(execution_reference, "执行引用")
        self.status = WorkflowNodeStatus.ACCEPTED
        self.updated_at = _utc(now, "节点接收时间")
        return _node_event(
            self,
            WorkflowEventType.NODE_ACCEPTED,
            transition_id,
            now,
            {"attempt_number": self.attempt_count, "execution_reference": self.execution_reference},
            run_id=run_id,
        )

    def succeed(
        self,
        *,
        result_summary: str,
        output_fingerprint: str | None,
        now: datetime,
        transition_id: str,
        run_id: UUID | None = None,
    ) -> WorkflowEvent:
        if self.status not in {WorkflowNodeStatus.RUNNING, WorkflowNodeStatus.ACCEPTED}:
            if (
                self.status is WorkflowNodeStatus.SUCCEEDED
                and self.result_summary == result_summary
            ):
                if self.output_fingerprint != output_fingerprint:
                    raise WorkflowIdempotencyConflictError("同一节点成功提交使用了不同的输出指纹。")
                return _node_event(
                    self,
                    WorkflowEventType.NODE_SUCCEEDED,
                    transition_id,
                    now,
                    {"attempt_number": self.attempt_count},
                    run_id=run_id,
                )
            raise WorkflowStateError("只有运行中或已接收节点可以成功。")
        self.status = WorkflowNodeStatus.SUCCEEDED
        self.result_summary = _text(result_summary, "节点结果摘要")
        self.output_fingerprint = _fingerprint(output_fingerprint, "输出指纹")
        self.execution_reference = None
        self.updated_at = _utc(now, "节点完成时间")
        return _node_event(
            self,
            WorkflowEventType.NODE_SUCCEEDED,
            transition_id,
            now,
            {"attempt_number": self.attempt_count},
            run_id=run_id,
        )

    def fail(
        self,
        *,
        error_code: str,
        retryable: bool,
        now: datetime,
        transition_id: str,
        run_id: UUID | None = None,
    ) -> WorkflowEvent:
        self._require_active()
        code = _text(error_code, "错误码")
        if not _SAFE_ERROR.fullmatch(code):
            raise WorkflowValidationError("错误码格式无效。")
        self.failure_code = code
        self.execution_reference = None
        if retryable and self.attempt_count < self.max_attempts:
            self.status = WorkflowNodeStatus.QUEUED
            event_type = WorkflowEventType.NODE_RETRY_SCHEDULED
        else:
            self.status = WorkflowNodeStatus.FAILED
            event_type = WorkflowEventType.NODE_FAILED
        self.updated_at = _utc(now, "节点失败时间")
        return _node_event(
            self,
            event_type,
            transition_id,
            now,
            {"attempt_number": self.attempt_count, "error_code": code},
            run_id=run_id,
        )

    def skip(
        self, *, reason: str, now: datetime, transition_id: str, run_id: UUID | None = None
    ) -> WorkflowEvent:
        if self.status is WorkflowNodeStatus.SKIPPED:
            normalized_reason = _text(reason, "跳过原因")
            return _node_event(
                self,
                WorkflowEventType.NODE_SKIPPED,
                transition_id,
                now,
                {"skip_reason": self.result_summary or normalized_reason},
                run_id=run_id,
            )
        if self.status is not WorkflowNodeStatus.QUEUED:
            raise WorkflowStateError("只有 queued 节点可以跳过。")
        self.result_summary = _text(reason, "跳过原因")
        self.status = WorkflowNodeStatus.SKIPPED
        self.updated_at = _utc(now, "节点跳过时间")
        return _node_event(
            self,
            WorkflowEventType.NODE_SKIPPED,
            transition_id,
            now,
            {"skip_reason": self.result_summary},
            run_id=run_id,
        )

    def request_cancel(
        self, *, now: datetime, transition_id: str, run_id: UUID | None = None
    ) -> WorkflowEvent:
        if self.status in {WorkflowNodeStatus.RUNNING, WorkflowNodeStatus.ACCEPTED}:
            self.status = WorkflowNodeStatus.CANCEL_REQUESTED
            self.updated_at = _utc(now, "节点取消时间")
            return _node_event(
                self,
                WorkflowEventType.NODE_CANCEL_REQUESTED,
                transition_id,
                now,
                {"attempt_number": self.attempt_count},
                run_id=run_id,
            )
        if self.status is WorkflowNodeStatus.QUEUED:
            self.status = WorkflowNodeStatus.CANCELLED
            self.updated_at = _utc(now, "节点取消时间")
            return _node_event(
                self,
                WorkflowEventType.NODE_CANCELLED,
                transition_id,
                now,
                {"cancel_mode": "queued"},
                run_id=run_id,
            )
        raise WorkflowStateError("当前节点状态不能取消。")

    def confirm_cancel(
        self, *, now: datetime, transition_id: str, run_id: UUID | None = None
    ) -> WorkflowEvent:
        if self.status is WorkflowNodeStatus.CANCELLED:
            return _node_event(
                self,
                WorkflowEventType.NODE_CANCELLED,
                transition_id,
                now,
                {"cancel_mode": "confirmed"},
                run_id=run_id,
            )
        if self.status is not WorkflowNodeStatus.CANCEL_REQUESTED:
            raise WorkflowStateError("节点未请求取消。")
        self.status = WorkflowNodeStatus.CANCELLED
        self.updated_at = _utc(now, "节点取消确认时间")
        return _node_event(
            self,
            WorkflowEventType.NODE_CANCELLED,
            transition_id,
            now,
            {"attempt_number": self.attempt_count, "cancel_mode": "confirmed"},
            run_id=run_id,
        )

    def _require_active(self) -> None:
        if self.status not in {WorkflowNodeStatus.RUNNING, WorkflowNodeStatus.ACCEPTED}:
            raise WorkflowStateError("节点不在可执行状态。")


@dataclass(slots=True)
class WorkflowRun:
    workflow_code: str
    workflow_version: str
    owner_subject: str
    idempotency_key: str
    input_fingerprint: str
    nodes: list[WorkflowNodeRun]
    status: WorkflowRunStatus = WorkflowRunStatus.QUEUED
    result_summary: str | None = None
    failure_code: str | None = None
    cancel_requested_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    events: list[WorkflowEvent] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def create(
        cls,
        *,
        version: WorkflowVersion,
        owner_subject: str,
        idempotency_key: str,
        input_fingerprint: str,
        now: datetime,
    ) -> "WorkflowRun":
        normalized_now = _utc(now, "Run 创建时间")
        run = cls(
            workflow_code=version.workflow_code,
            workflow_version=version.version,
            owner_subject=_text(owner_subject, "主体标识"),
            idempotency_key=_text(idempotency_key, "幂等键"),
            input_fingerprint=_text(input_fingerprint, "输入指纹"),
            nodes=[
                WorkflowNodeRun(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    capability_code=node.capability_code,
                    max_attempts=node.max_attempts,
                    created_at=normalized_now,
                    updated_at=normalized_now,
                )
                for node in version.nodes
            ],
            created_at=normalized_now,
            updated_at=normalized_now,
        )
        run._append_event(
            "create",
            WorkflowEventType.RUN_CREATED,
            normalized_now,
            {"workflow_code": run.workflow_code, "workflow_version": run.workflow_version},
        )
        return run

    @property
    def version_key(self) -> str:
        return f"{self.workflow_code}:{self.workflow_version}"

    def node(self, node_id: str) -> WorkflowNodeRun:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise WorkflowValidationError("Run 节点不存在。")

    def ready_nodes(self, version: WorkflowVersion) -> tuple[str, ...]:
        return tuple(
            node.node_id
            for node in self.nodes
            if node.status is WorkflowNodeStatus.QUEUED
            and all(
                self.node(predecessor).status is WorkflowNodeStatus.SUCCEEDED
                for predecessor in version.predecessors(node.node_id)
            )
        )

    def start_node(
        self, *, version: WorkflowVersion, node_id: str, now: datetime, command_id: str
    ) -> WorkflowEvent:
        if self.status in {
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.SUCCEEDED,
        }:
            raise WorkflowStateError("当前 Run 不能开始节点。")
        if node_id not in self.ready_nodes(version):
            raise WorkflowStateError("节点前置依赖尚未满足。")
        node = self.node(node_id)
        event = node.start(now=now, transition_id=f"{command_id}:start", run_id=self.id)
        if self.status is WorkflowRunStatus.QUEUED:
            self.status = WorkflowRunStatus.RUNNING
            self._append_event(f"{command_id}:run-start", WorkflowEventType.RUN_STARTED, now, {})
        self._append_existing(event)
        self.updated_at = _utc(now, "Run 开始时间")
        return event

    def accept_node(
        self,
        *,
        node_id: str,
        execution_reference: str,
        now: datetime,
        command_id: str,
    ) -> WorkflowEvent:
        if self.status in {
            WorkflowRunStatus.CANCEL_REQUESTED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.SUCCEEDED,
        }:
            raise WorkflowStateError("当前 Run 不能接收节点结果。")
        node = self.node(node_id)
        was_accepted = node.status is WorkflowNodeStatus.ACCEPTED
        event = node.accept(
            execution_reference=execution_reference,
            now=now,
            transition_id=f"{command_id}:accept",
            run_id=self.id,
        )
        if was_accepted:
            existing = self._find_latest_node_event(node_id, WorkflowEventType.NODE_ACCEPTED)
            if existing is not None:
                return existing
        self.status = WorkflowRunStatus.ACCEPTED
        self._append_existing(event)
        self._append_event(
            f"{command_id}:run-accepted",
            WorkflowEventType.RUN_ACCEPTED,
            now,
            {"node_id": node_id},
        )
        self.updated_at = _utc(now, "Run 接收时间")
        return event

    def succeed_node(
        self,
        *,
        version: WorkflowVersion,
        node_id: str,
        result_summary: str,
        output_fingerprint: str | None,
        now: datetime,
        command_id: str,
    ) -> WorkflowEvent:
        node = self.node(node_id)
        if node.status is WorkflowNodeStatus.SUCCEEDED:
            if (
                node.result_summary != result_summary
                or node.output_fingerprint != output_fingerprint
            ):
                raise WorkflowIdempotencyConflictError("同一节点成功提交使用了不同的结果。")
            existing = self._find_latest_node_event(node_id, WorkflowEventType.NODE_SUCCEEDED)
            if existing is not None:
                return existing
        event = node.succeed(
            result_summary=result_summary,
            output_fingerprint=output_fingerprint,
            now=now,
            transition_id=f"{command_id}:succeed",
            run_id=self.id,
        )
        self._append_existing(event)
        self._refresh_status(version, now, command_id)
        return event

    def fail_node(
        self,
        *,
        version: WorkflowVersion,
        node_id: str,
        error_code: str,
        retryable: bool,
        now: datetime,
        command_id: str,
    ) -> WorkflowEvent:
        node = self.node(node_id)
        event = node.fail(
            error_code=error_code,
            retryable=retryable,
            now=now,
            transition_id=f"{command_id}:fail",
            run_id=self.id,
        )
        self._append_existing(event)
        if node.status is WorkflowNodeStatus.FAILED:
            self.status = WorkflowRunStatus.FAILED
            self.failure_code = node.failure_code
            self._append_event(
                f"{command_id}:run-failed",
                WorkflowEventType.RUN_FAILED,
                now,
                {"node_id": node_id, "error_code": node.failure_code},
            )
        self.updated_at = _utc(now, "Run 失败时间")
        return event

    def skip_node(
        self,
        *,
        version: WorkflowVersion,
        node_id: str,
        reason: str,
        now: datetime,
        command_id: str,
    ) -> WorkflowEvent:
        node = self.node(node_id)
        event = node.skip(
            reason=reason,
            now=now,
            transition_id=f"{command_id}:skip",
            run_id=self.id,
        )
        self._append_existing(event)
        self._refresh_status(version, now, command_id)
        return event

    def request_cancel(self, *, now: datetime, command_id: str) -> None:
        if self.status in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
        }:
            raise WorkflowStateError("当前 Run 已经是终态。")
        if self.status is WorkflowRunStatus.CANCEL_REQUESTED:
            return
        self.status = WorkflowRunStatus.CANCEL_REQUESTED
        self.cancel_requested_at = _utc(now, "Run 取消时间")
        self._append_event(
            f"{command_id}:run-cancel-requested",
            WorkflowEventType.RUN_CANCEL_REQUESTED,
            now,
            {},
        )
        for node in self.nodes:
            if node.status in {
                WorkflowNodeStatus.QUEUED,
                WorkflowNodeStatus.RUNNING,
                WorkflowNodeStatus.ACCEPTED,
            }:
                event = node.request_cancel(
                    now=now,
                    transition_id=f"{command_id}:{node.node_id}:cancel",
                    run_id=self.id,
                )
                self._append_existing(event)
        if all(
            node.status
            in {
                WorkflowNodeStatus.CANCELLED,
                WorkflowNodeStatus.SUCCEEDED,
                WorkflowNodeStatus.SKIPPED,
            }
            for node in self.nodes
        ):
            self.status = WorkflowRunStatus.CANCELLED
            self._append_event(f"{command_id}:complete", WorkflowEventType.RUN_CANCELLED, now, {})
        self.updated_at = _utc(now, "Run 取消时间")

    def confirm_node_cancel(self, *, node_id: str, now: datetime, command_id: str) -> WorkflowEvent:
        event = self.node(node_id).confirm_cancel(
            now=now,
            transition_id=f"{command_id}:confirm",
            run_id=self.id,
        )
        self._append_existing(event)
        if self.status is WorkflowRunStatus.CANCEL_REQUESTED and all(
            node.status
            in {
                WorkflowNodeStatus.CANCELLED,
                WorkflowNodeStatus.SUCCEEDED,
                WorkflowNodeStatus.SKIPPED,
            }
            for node in self.nodes
        ):
            self.status = WorkflowRunStatus.CANCELLED
            self._append_event(command_id, WorkflowEventType.RUN_CANCELLED, now, {})
        self.updated_at = _utc(now, "Run 取消确认时间")
        return event

    def _refresh_status(self, version: WorkflowVersion, now: datetime, command_id: str) -> None:
        if all(
            node.status in {WorkflowNodeStatus.SUCCEEDED, WorkflowNodeStatus.SKIPPED}
            for node in self.nodes
        ):
            self.status = WorkflowRunStatus.SUCCEEDED
            self.result_summary = "Workflow 节点已全部完成。"
            self._append_event(command_id, WorkflowEventType.RUN_SUCCEEDED, now, {})
        elif any(node.status is WorkflowNodeStatus.ACCEPTED for node in self.nodes):
            self.status = WorkflowRunStatus.ACCEPTED
        elif self.status is WorkflowRunStatus.ACCEPTED:
            self.status = WorkflowRunStatus.RUNNING

    def _append_event(
        self,
        transition_id: str,
        event_type: WorkflowEventType,
        now: datetime,
        metadata: Mapping[str, object],
    ) -> WorkflowEvent:
        if any(event.transition_id == transition_id for event in self.events):
            existing = next(event for event in self.events if event.transition_id == transition_id)
            return existing
        event = WorkflowEvent(
            self.id,
            len(self.events) + 1,
            transition_id,
            event_type,
            dict(metadata),
            _utc(now, "事件时间"),
        )
        self.events.append(event)
        return event

    def _append_existing(self, event: WorkflowEvent) -> None:
        if any(existing.transition_id == event.transition_id for existing in self.events):
            return
        self.events.append(
            WorkflowEvent(
                self.id,
                len(self.events) + 1,
                event.transition_id,
                event.event_type,
                dict(event.metadata),
                event.created_at,
            )
        )

    def _find_latest_node_event(
        self, node_id: str, event_type: WorkflowEventType
    ) -> WorkflowEvent | None:
        for event in reversed(self.events):
            if event.event_type is event_type and event.metadata.get("node_id") == node_id:
                return event
        return None


def _node_event(
    node: WorkflowNodeRun,
    event_type: WorkflowEventType,
    transition_id: str,
    now: datetime,
    metadata: Mapping[str, object],
    *,
    run_id: UUID | None = None,
) -> WorkflowEvent:
    if not transition_id.strip():
        raise WorkflowValidationError("节点转换标识不能为空。")
    return WorkflowEvent(
        run_id=run_id or UUID(int=0),
        sequence=1,
        transition_id=transition_id,
        event_type=event_type,
        metadata={"node_id": node.node_id, **dict(metadata)},
        created_at=_utc(now, "节点事件时间"),
    )


def _assert_acyclic(node_ids: list[str], edges: tuple[WorkflowEdgeDefinition, ...]) -> None:
    graph = {node_id: [] for node_id in node_ids}
    for edge in edges:
        graph[edge.source_node_id].append(edge.target_node_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise WorkflowValidationError("Workflow 边不能形成循环。")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child in graph[node_id]:
            visit(child)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in node_ids:
        visit(node_id)


__all__ = [
    "WorkflowEdgeDefinition",
    "WorkflowEvent",
    "WorkflowEventType",
    "WorkflowIdempotencyConflictError",
    "WorkflowNodeDefinition",
    "WorkflowNodeRun",
    "WorkflowNodeStatus",
    "WorkflowNodeType",
    "WorkflowRun",
    "WorkflowRunStatus",
    "WorkflowStateError",
    "WorkflowValidationError",
    "WorkflowVersion",
]
