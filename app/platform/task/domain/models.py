from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping
from uuid import UUID, uuid4

from app.platform.task.errors import (
    TaskIdempotencyConflictError,
    TaskLeaseRejectedError,
    TaskStateTransitionError,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}必须是非空字符串。")
    return value.strip()


def _require_utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label}必须是带时区的时间。")
    return value.astimezone(timezone.utc)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AttemptStatus(StrEnum):
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class FailureCategory(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    LEASE_EXPIRED = "lease_expired"


class TaskEventType(StrEnum):
    TASK_CREATED = "TASK_CREATED"
    TASK_CLAIMED = "TASK_CLAIMED"
    TASK_CANCEL_REQUESTED = "TASK_CANCEL_REQUESTED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    TASK_FAILED = "TASK_FAILED"
    TASK_RETRY_SCHEDULED = "TASK_RETRY_SCHEDULED"
    TASK_REQUEUED = "TASK_REQUEUED"
    TASK_RETRY_REQUESTED = "TASK_RETRY_REQUESTED"
    TASK_RECOVERED = "TASK_RECOVERED"


_SENSITIVE_METADATA_PARTS = (
    "input",
    "token",
    "exception",
    "traceback",
    "authorization",
    "api_key",
    "provider_response",
    "raw_response",
    "credential",
    "password",
    "secret",
)
_SAFE_FAILURE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_SAFE_FINGERPRINT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_EVENT_METADATA_FIELDS: dict[TaskEventType, frozenset[str]] = {
    TaskEventType.TASK_CREATED: frozenset({"task_type"}),
    TaskEventType.TASK_CLAIMED: frozenset({"attempt_number", "claim_id", "worker_id"}),
    TaskEventType.TASK_CANCEL_REQUESTED: frozenset(),
    TaskEventType.TASK_CANCELLED: frozenset({"attempt_number", "cancel_mode"}),
    TaskEventType.TASK_SUCCEEDED: frozenset({"attempt_number", "result_fingerprint"}),
    TaskEventType.TASK_FAILED: frozenset(
        {"attempt_number", "failure_category", "failure_code"}
    ),
    TaskEventType.TASK_RETRY_SCHEDULED: frozenset(
        {"attempt_number", "failure_category", "failure_code"}
    ),
    TaskEventType.TASK_REQUEUED: frozenset(),
    TaskEventType.TASK_RETRY_REQUESTED: frozenset(),
    TaskEventType.TASK_RECOVERED: frozenset({"attempt_number", "outcome"}),
}
_OPTIONAL_EVENT_METADATA_FIELDS: dict[TaskEventType, frozenset[str]] = {
    TaskEventType.TASK_CANCELLED: frozenset({"attempt_number"}),
}


def _require_safe_failure_code(value: object) -> str:
    code = _require_text(value, "失败码")
    if _SAFE_FAILURE_CODE.fullmatch(code) is None:
        raise ValueError("失败码必须是安全分类代码。")
    return code


def _require_safe_fingerprint(value: object) -> str:
    fingerprint = _require_text(value, "结果指纹")
    if _SAFE_FINGERPRINT.fullmatch(fingerprint) is None:
        raise ValueError("结果指纹必须是安全标识。")
    return fingerprint


def _safe_metadata(
    *, event_type: TaskEventType, metadata: Mapping[str, object]
) -> dict[str, str | int]:
    allowed_fields = _EVENT_METADATA_FIELDS[event_type]
    optional_fields = _OPTIONAL_EVENT_METADATA_FIELDS.get(event_type, frozenset())
    normalized: dict[str, str | int] = {}
    for key, value in metadata.items():
        key_text = _require_text(key, "事件元数据键")
        if any(part in key_text.lower() for part in _SENSITIVE_METADATA_PARTS):
            raise ValueError("事件元数据不能包含敏感内部字段。")
        if key_text not in allowed_fields:
            raise ValueError("事件元数据包含当前事件不允许的字段。")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("事件元数据不能包含非有限浮点数。")
        if key_text == "attempt_number":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("事件尝试序号必须是正整数。")
            normalized[key_text] = value
        elif key_text == "failure_code":
            normalized[key_text] = _require_safe_failure_code(value)
        elif key_text == "result_fingerprint":
            normalized[key_text] = _require_safe_fingerprint(value)
        else:
            normalized[key_text] = _require_text(value, "事件元数据值")
    required_fields = allowed_fields - optional_fields
    if not required_fields.issubset(normalized):
        raise ValueError("事件元数据缺少当前事件要求的安全字段。")
    # 领域阶段先验证标准 JSON，避免 TM-02 的 JSON 持久化才暴露不兼容数据。
    json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    return normalized


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: UUID
    sequence: int
    transition_id: str
    event_type: TaskEventType
    metadata: dict[str, str | int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.task_id, UUID):
            raise ValueError("事件标识和任务标识必须是 UUID。")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence <= 0
        ):
            raise ValueError("事件顺序必须是正整数。")
        object.__setattr__(self, "transition_id", _require_text(self.transition_id, "转换标识"))
        if not isinstance(self.event_type, TaskEventType):
            raise ValueError("任务事件类型无效。")
        object.__setattr__(
            self,
            "metadata",
            _safe_metadata(event_type=self.event_type, metadata=self.metadata),
        )
        object.__setattr__(self, "created_at", _require_utc(self.created_at, "事件时间"))


@dataclass(slots=True)
class TaskAttempt:
    task_id: UUID
    number: int
    worker_id: str
    claim_id: str
    lease_token: str
    lease_expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    status: AttemptStatus = AttemptStatus.ACTIVE
    renewal_sequence: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    finished_at: datetime | None = None
    failure_category: FailureCategory | None = None
    failure_code: str | None = None
    result_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.task_id, UUID):
            raise ValueError("尝试标识和任务标识必须是 UUID。")
        if isinstance(self.number, bool) or not isinstance(self.number, int) or self.number <= 0:
            raise ValueError("尝试序号必须是正整数。")
        self.worker_id = _require_text(self.worker_id, "执行者标识")
        self.claim_id = _require_text(self.claim_id, "领取标识")
        self.lease_token = _require_text(self.lease_token, "租约令牌")
        self.lease_expires_at = _require_utc(self.lease_expires_at, "租约到期时间")
        self.created_at = _require_utc(self.created_at, "尝试创建时间")
        if self.lease_expires_at <= self.created_at:
            raise ValueError("租约到期时间必须晚于尝试创建时间。")
        if not isinstance(self.status, AttemptStatus):
            raise ValueError("尝试状态无效。")
        if isinstance(self.renewal_sequence, bool) or self.renewal_sequence < 0:
            raise ValueError("续租序号必须是非负整数。")
        if self.finished_at is not None:
            self.finished_at = _require_utc(self.finished_at, "尝试完成时间")

    @property
    def is_active(self) -> bool:
        return self.status is AttemptStatus.ACTIVE

    def assert_valid_lease(self, *, lease_token: str, now: datetime) -> None:
        if self.lease_token != _require_text(lease_token, "租约令牌"):
            raise TaskLeaseRejectedError("租约令牌不匹配。")
        if not self.is_active or _require_utc(now, "当前时间") >= self.lease_expires_at:
            raise TaskLeaseRejectedError("租约已失效。")

    def renew(
        self,
        *,
        lease_token: str,
        renewal_sequence: int,
        lease_expires_at: datetime,
        now: datetime,
    ) -> None:
        if self.lease_token != _require_text(lease_token, "租约令牌"):
            raise TaskLeaseRejectedError("租约令牌不匹配。")
        if not self.is_active:
            raise TaskLeaseRejectedError("非活动尝试不能续租。")
        if isinstance(renewal_sequence, bool) or not isinstance(renewal_sequence, int):
            raise ValueError("续租序号必须是正整数。")
        normalized_expiry = _require_utc(lease_expires_at, "租约到期时间")
        if renewal_sequence == self.renewal_sequence:
            if normalized_expiry != self.lease_expires_at:
                raise TaskIdempotencyConflictError("同一续租序号使用了不同的到期时间。")
            return
        if renewal_sequence <= self.renewal_sequence:
            raise TaskStateTransitionError("续租序号必须严格递增。")
        self.assert_valid_lease(lease_token=lease_token, now=now)
        if normalized_expiry <= self.lease_expires_at:
            raise ValueError("续租到期时间必须延后。")
        self.renewal_sequence = renewal_sequence
        self.lease_expires_at = normalized_expiry

    def finish(
        self,
        *,
        status: AttemptStatus,
        now: datetime,
        failure_category: FailureCategory | None = None,
        failure_code: str | None = None,
        result_fingerprint: str | None = None,
    ) -> None:
        if not self.is_active:
            raise TaskStateTransitionError("只有活动尝试可以结束。")
        if status is AttemptStatus.ACTIVE:
            raise ValueError("尝试结束状态不能是 active。")
        self.status = status
        self.finished_at = _require_utc(now, "尝试完成时间")
        self.failure_category = failure_category
        self.failure_code = _require_safe_failure_code(failure_code) if failure_code else None
        self.result_fingerprint = (
            _require_safe_fingerprint(result_fingerprint) if result_fingerprint else None
        )


@dataclass(slots=True)
class Task:
    task_type: str
    owner_subject: str
    idempotency_key: str
    input_fingerprint: str
    max_attempts: int
    available_at: datetime
    id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.QUEUED
    display_metadata: dict[str, str] = field(default_factory=dict)
    allow_manual_retry: bool = True
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    cancel_requested_at: datetime | None = None
    result_summary: str | None = None
    result_fingerprint: str | None = None
    failure_code: str | None = None
    attempts: list[TaskAttempt] = field(default_factory=list)
    events: list[TaskEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("任务标识必须是 UUID。")
        self.task_type = _require_text(self.task_type, "任务类型")
        self.owner_subject = _require_text(self.owner_subject, "任务归属主体")
        self.idempotency_key = _require_text(self.idempotency_key, "幂等键")
        self.input_fingerprint = _require_text(self.input_fingerprint, "输入指纹")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise ValueError("最大尝试次数必须是正整数。")
        if self.max_attempts <= 0:
            raise ValueError("最大尝试次数必须是正整数。")
        self.available_at = _require_utc(self.available_at, "可执行时间")
        self.created_at = _require_utc(self.created_at, "任务创建时间")
        self.updated_at = _require_utc(self.updated_at, "任务更新时间")
        if not isinstance(self.status, TaskStatus):
            raise ValueError("任务状态无效。")
        if not isinstance(self.allow_manual_retry, bool):
            raise ValueError("手动重试策略必须是布尔值。")
        if not isinstance(self.display_metadata, dict) or any(
            not isinstance(key, str) or not key.strip() or not isinstance(value, str)
            for key, value in self.display_metadata.items()
        ):
            raise ValueError("展示元数据必须是字符串键值对。")
        self._validate_invariants()

    @classmethod
    def create(
        cls,
        *,
        task_type: str,
        owner_subject: str,
        idempotency_key: str,
        input_fingerprint: str,
        max_attempts: int,
        display_metadata: Mapping[str, str] | None,
        allow_manual_retry: bool,
        now: datetime,
    ) -> Task:
        normalized_now = _require_utc(now, "创建时间")
        task = cls(
            task_type=task_type,
            owner_subject=owner_subject,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            max_attempts=max_attempts,
            available_at=normalized_now,
            display_metadata=dict(display_metadata or {}),
            allow_manual_retry=allow_manual_retry,
            created_at=normalized_now,
            updated_at=normalized_now,
        )
        task._append_event(
            transition_id=f"create:{task.idempotency_key}",
            event_type=TaskEventType.TASK_CREATED,
            metadata={"task_type": task.task_type},
            now=normalized_now,
        )
        return task

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def active_attempt(self) -> TaskAttempt | None:
        active = [attempt for attempt in self.attempts if attempt.is_active]
        if len(active) > 1:
            raise TaskStateTransitionError("一个任务不能同时存在多个活动尝试。")
        return active[0] if active else None

    def find_attempt(self, attempt_id: UUID) -> TaskAttempt:
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                return attempt
        raise TaskStateTransitionError("尝试不属于当前任务。")

    def find_attempt_by_claim(self, *, worker_id: str, claim_id: str) -> TaskAttempt | None:
        normalized_worker = _require_text(worker_id, "执行者标识")
        normalized_claim = _require_text(claim_id, "领取标识")
        for attempt in self.attempts:
            if attempt.worker_id == normalized_worker and attempt.claim_id == normalized_claim:
                return attempt
        return None

    def claim(
        self,
        *,
        worker_id: str,
        claim_id: str,
        lease_token: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> TaskAttempt:
        normalized_now = _require_utc(now, "领取时间")
        if self.status is not TaskStatus.QUEUED:
            raise TaskStateTransitionError("只有 queued 任务可以领取。")
        if normalized_now < self.available_at:
            raise TaskStateTransitionError("任务尚未到达可执行时间。")
        if self.attempt_count >= self.max_attempts:
            raise TaskStateTransitionError("任务已耗尽最大尝试次数。")
        attempt = TaskAttempt(
            task_id=self.id,
            number=self.attempt_count + 1,
            worker_id=worker_id,
            claim_id=claim_id,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            created_at=normalized_now,
        )
        self.attempts.append(attempt)
        self.status = TaskStatus.RUNNING
        self.updated_at = normalized_now
        # 领取是 TM-01 唯一的执行启动边界，不额外追加第二条“开始”事件。
        self._append_event(
            transition_id=f"claim:{attempt.claim_id}",
            event_type=TaskEventType.TASK_CLAIMED,
            metadata={
                "attempt_number": attempt.number,
                "claim_id": attempt.claim_id,
                "worker_id": attempt.worker_id,
            },
            now=normalized_now,
        )
        self._validate_invariants()
        return attempt

    def renew_lease(
        self,
        *,
        attempt_id: UUID,
        lease_token: str,
        renewal_sequence: int,
        lease_expires_at: datetime,
        now: datetime,
    ) -> TaskAttempt:
        attempt = self.find_attempt(attempt_id)
        if not attempt.is_active:
            raise TaskLeaseRejectedError("尝试不再持有有效租约。")
        if self.status not in {TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED}:
            raise TaskStateTransitionError("当前任务状态不能续租。")
        if attempt is not self.active_attempt:
            raise TaskLeaseRejectedError("尝试不是当前活动尝试。")
        attempt.renew(
            lease_token=lease_token,
            renewal_sequence=renewal_sequence,
            lease_expires_at=lease_expires_at,
            now=now,
        )
        return attempt

    def request_cancel(self, *, command_id: str, now: datetime) -> None:
        normalized_now = _require_utc(now, "取消时间")
        transition_id = f"cancel:{_require_text(command_id, '取消命令标识')}"
        if self.status in {TaskStatus.QUEUED, TaskStatus.RETRY_WAIT}:
            self.cancel_requested_at = normalized_now
            self.status = TaskStatus.CANCELLED
            self.updated_at = normalized_now
            self._append_event(
                transition_id=transition_id,
                event_type=TaskEventType.TASK_CANCELLED,
                metadata={"cancel_mode": "queued"},
                now=normalized_now,
            )
        elif self.status is TaskStatus.RUNNING:
            self.cancel_requested_at = normalized_now
            self.status = TaskStatus.CANCEL_REQUESTED
            self.updated_at = normalized_now
            self._append_event(
                transition_id=transition_id,
                event_type=TaskEventType.TASK_CANCEL_REQUESTED,
                metadata={},
                now=normalized_now,
            )
        else:
            raise TaskStateTransitionError("当前任务状态不能取消。")
        self._validate_invariants()

    def confirm_cancel(
        self,
        *,
        attempt_id: UUID,
        lease_token: str,
        now: datetime,
    ) -> None:
        attempt = self.find_attempt(attempt_id)
        if self.status is TaskStatus.CANCELLED and attempt.status is AttemptStatus.CANCELLED:
            if attempt.lease_token != _require_text(lease_token, "租约令牌"):
                raise TaskLeaseRejectedError("租约令牌不匹配。")
            return
        if not attempt.is_active:
            raise TaskLeaseRejectedError("尝试不再持有有效租约。")
        if self.status is not TaskStatus.CANCEL_REQUESTED:
            raise TaskStateTransitionError("当前任务未请求取消。")
        self._assert_active_lease(attempt=attempt, lease_token=lease_token, now=now)
        normalized_now = _require_utc(now, "取消确认时间")
        attempt.finish(status=AttemptStatus.CANCELLED, now=normalized_now)
        self.status = TaskStatus.CANCELLED
        self.updated_at = normalized_now
        self._append_event(
            transition_id=f"cancelled:{attempt.id}",
            event_type=TaskEventType.TASK_CANCELLED,
            metadata={"attempt_number": attempt.number, "cancel_mode": "confirmed"},
            now=normalized_now,
        )
        self._validate_invariants()

    def complete(
        self,
        *,
        attempt_id: UUID,
        lease_token: str,
        result_fingerprint: str,
        result_summary: str,
        now: datetime,
    ) -> None:
        attempt = self.find_attempt(attempt_id)
        normalized_fingerprint = _require_safe_fingerprint(result_fingerprint)
        if self.status is TaskStatus.SUCCEEDED and attempt.status is AttemptStatus.SUCCEEDED:
            self._assert_same_terminal_result(
                attempt=attempt,
                lease_token=lease_token,
                result_fingerprint=normalized_fingerprint,
            )
            return
        if not attempt.is_active:
            raise TaskLeaseRejectedError("尝试不再持有有效租约。")
        if self.status is not TaskStatus.RUNNING:
            raise TaskStateTransitionError("只有 running 任务可以提交成功结果。")
        self._assert_active_lease(attempt=attempt, lease_token=lease_token, now=now)
        normalized_now = _require_utc(now, "完成时间")
        normalized_summary = _require_text(result_summary, "结果摘要")
        attempt.finish(
            status=AttemptStatus.SUCCEEDED,
            now=normalized_now,
            result_fingerprint=normalized_fingerprint,
        )
        self.status = TaskStatus.SUCCEEDED
        self.result_fingerprint = normalized_fingerprint
        self.result_summary = normalized_summary
        self.failure_code = None
        self.updated_at = normalized_now
        self._append_event(
            transition_id=f"succeeded:{attempt.id}:{normalized_fingerprint}",
            event_type=TaskEventType.TASK_SUCCEEDED,
            metadata={
                "attempt_number": attempt.number,
                "result_fingerprint": normalized_fingerprint,
            },
            now=normalized_now,
        )
        self._validate_invariants()

    def fail(
        self,
        *,
        attempt_id: UUID,
        lease_token: str,
        failure_category: FailureCategory,
        failure_code: str,
        result_fingerprint: str,
        retry_at: datetime | None,
        now: datetime,
    ) -> None:
        attempt = self.find_attempt(attempt_id)
        normalized_fingerprint = _require_safe_fingerprint(result_fingerprint)
        if (
            self.status in {TaskStatus.RETRY_WAIT, TaskStatus.FAILED}
            and attempt.status is AttemptStatus.FAILED
        ):
            self._assert_same_terminal_result(
                attempt=attempt,
                lease_token=lease_token,
                result_fingerprint=normalized_fingerprint,
            )
            return
        if not attempt.is_active:
            raise TaskLeaseRejectedError("尝试不再持有有效租约。")
        if self.status is not TaskStatus.RUNNING:
            raise TaskStateTransitionError("只有 running 任务可以提交失败结果。")
        if not isinstance(failure_category, FailureCategory):
            raise ValueError("失败分类无效。")
        self._assert_active_lease(attempt=attempt, lease_token=lease_token, now=now)
        normalized_now = _require_utc(now, "失败时间")
        normalized_code = _require_safe_failure_code(failure_code)
        is_retryable = (
            failure_category is FailureCategory.TRANSIENT and self.attempt_count < self.max_attempts
        )
        normalized_retry_at = None
        if is_retryable:
            normalized_retry_at = _require_utc(retry_at, "重试时间")
            if normalized_retry_at < normalized_now:
                raise ValueError("重试时间不能早于失败时间。")
        attempt.finish(
            status=AttemptStatus.FAILED,
            now=normalized_now,
            failure_category=failure_category,
            failure_code=normalized_code,
            result_fingerprint=normalized_fingerprint,
        )
        self.failure_code = normalized_code
        self.result_fingerprint = normalized_fingerprint
        self.result_summary = None
        self.updated_at = normalized_now
        if is_retryable:
            self.status = TaskStatus.RETRY_WAIT
            self.available_at = normalized_retry_at
            event_type = TaskEventType.TASK_RETRY_SCHEDULED
        else:
            self.status = TaskStatus.FAILED
            event_type = TaskEventType.TASK_FAILED
        self._append_event(
            transition_id=f"failed:{attempt.id}:{normalized_fingerprint}",
            event_type=event_type,
            metadata={
                "attempt_number": attempt.number,
                "failure_category": failure_category.value,
                "failure_code": normalized_code,
            },
            now=normalized_now,
        )
        self._validate_invariants()

    def requeue_due(self, *, command_id: str, now: datetime) -> None:
        normalized_now = _require_utc(now, "重新入队时间")
        if self.status is not TaskStatus.RETRY_WAIT:
            raise TaskStateTransitionError("只有 retry_wait 任务可以重新入队。")
        if normalized_now < self.available_at:
            raise TaskStateTransitionError("重试退避尚未到期。")
        self.status = TaskStatus.QUEUED
        self.available_at = normalized_now
        self.updated_at = normalized_now
        self._append_event(
            transition_id=f"requeue:{_require_text(command_id, '重新入队命令标识')}",
            event_type=TaskEventType.TASK_REQUEUED,
            metadata={},
            now=normalized_now,
        )
        self._validate_invariants()

    def request_manual_retry(self, *, command_id: str, now: datetime) -> None:
        normalized_now = _require_utc(now, "手动重试时间")
        if self.status is not TaskStatus.FAILED:
            raise TaskStateTransitionError("只有 failed 任务可以手动重试。")
        if not self.allow_manual_retry or self.attempt_count >= self.max_attempts:
            raise TaskStateTransitionError("当前任务不允许手动重试。")
        self.status = TaskStatus.QUEUED
        self.available_at = normalized_now
        self.failure_code = None
        self.result_fingerprint = None
        self.updated_at = normalized_now
        self._append_event(
            transition_id=f"manual-retry:{_require_text(command_id, '手动重试命令标识')}",
            event_type=TaskEventType.TASK_RETRY_REQUESTED,
            metadata={},
            now=normalized_now,
        )
        self._validate_invariants()

    def recover_expired_attempt(
        self,
        *,
        command_id: str,
        retry_at: datetime | None,
        now: datetime,
        attempt_id: UUID | None = None,
    ) -> None:
        normalized_now = _require_utc(now, "恢复时间")
        if self.status not in {TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED}:
            raise TaskStateTransitionError("当前任务状态不能恢复。")
        attempt = self.active_attempt
        if attempt is None or normalized_now < attempt.lease_expires_at:
            raise TaskStateTransitionError("当前任务没有过期 lease。")
        if attempt_id is not None and attempt.id != attempt_id:
            raise TaskStateTransitionError("恢复候选已不再是当前活动尝试。")
        attempt.finish(
            status=AttemptStatus.EXPIRED,
            now=normalized_now,
            failure_category=FailureCategory.LEASE_EXPIRED,
            failure_code="LEASE_EXPIRED",
        )
        outcome: TaskStatus
        if self.status is TaskStatus.CANCEL_REQUESTED:
            outcome = TaskStatus.CANCELLED
        elif self.attempt_count >= self.max_attempts:
            outcome = TaskStatus.FAILED
            self.failure_code = "LEASE_EXPIRED"
        elif retry_at is not None and _require_utc(retry_at, "恢复重试时间") > normalized_now:
            outcome = TaskStatus.RETRY_WAIT
            self.available_at = _require_utc(retry_at, "恢复重试时间")
        else:
            outcome = TaskStatus.QUEUED
            self.available_at = normalized_now
        self.status = outcome
        self.updated_at = normalized_now
        self._append_event(
            transition_id=f"recovered:{_require_text(command_id, '恢复命令标识')}",
            event_type=TaskEventType.TASK_RECOVERED,
            metadata={"attempt_number": attempt.number, "outcome": outcome.value},
            now=normalized_now,
        )
        self._validate_invariants()

    def _assert_active_lease(
        self,
        *,
        attempt: TaskAttempt,
        lease_token: str,
        now: datetime,
    ) -> None:
        if attempt is not self.active_attempt:
            raise TaskLeaseRejectedError("尝试不是当前活动尝试。")
        attempt.assert_valid_lease(lease_token=lease_token, now=now)

    @staticmethod
    def _assert_same_terminal_result(
        *,
        attempt: TaskAttempt,
        lease_token: str,
        result_fingerprint: str,
    ) -> None:
        if attempt.lease_token != _require_text(lease_token, "租约令牌"):
            raise TaskLeaseRejectedError("租约令牌不匹配。")
        if attempt.result_fingerprint != result_fingerprint:
            raise TaskIdempotencyConflictError("同一终态提交使用了不同的结果指纹。")

    def _append_event(
        self,
        *,
        transition_id: str,
        event_type: TaskEventType,
        metadata: Mapping[str, object],
        now: datetime,
    ) -> None:
        normalized_transition_id = _require_text(transition_id, "转换标识")
        if any(event.transition_id == normalized_transition_id for event in self.events):
            raise TaskIdempotencyConflictError("同一转换不能重复写入事件。")
        self.events.append(
            TaskEvent(
                task_id=self.id,
                sequence=len(self.events) + 1,
                transition_id=normalized_transition_id,
                event_type=event_type,
                metadata=dict(metadata),
                created_at=now,
            )
        )

    def _validate_invariants(self) -> None:
        if any(attempt.task_id != self.id for attempt in self.attempts):
            raise ValueError("任务不能包含其他任务的尝试。")
        if [attempt.number for attempt in self.attempts] != list(range(1, self.attempt_count + 1)):
            raise ValueError("尝试序号必须从一开始连续递增。")
        if any(event.task_id != self.id for event in self.events):
            raise ValueError("任务不能包含其他任务的事件。")
        if [event.sequence for event in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError("事件顺序必须从一开始连续递增。")
        transition_ids = [event.transition_id for event in self.events]
        if len(transition_ids) != len(set(transition_ids)):
            raise ValueError("同一任务的转换标识必须唯一。")
        active_count = sum(attempt.is_active for attempt in self.attempts)
        if self.status in {TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED}:
            if active_count != 1:
                raise ValueError("运行中或取消请求中的任务必须有一个活动尝试。")
        elif active_count != 0:
            raise ValueError("非运行任务不能保留活动尝试。")
        if self.status is TaskStatus.SUCCEEDED and not self.result_summary:
            raise ValueError("成功任务必须包含安全结果摘要。")
