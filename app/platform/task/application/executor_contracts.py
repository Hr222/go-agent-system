from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.platform.task.application.contracts import TaskView
from app.platform.task.domain import FailureCategory


@dataclass(frozen=True, slots=True)
class ClaimTaskCommand:
    """仅供受信任执行器领取任务，不是通用协议命令。"""

    task_id: UUID
    worker_id: str
    claim_id: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class RenewLeaseCommand:
    """仅供持有 lease 的受信任执行器续租。"""

    task_id: UUID
    attempt_id: UUID
    lease_token: str
    renewal_sequence: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConfirmCancellationCommand:
    """执行器在安全检查点确认协作式取消。"""

    task_id: UUID
    attempt_id: UUID
    lease_token: str


@dataclass(frozen=True, slots=True)
class CompleteTaskCommand:
    task_id: UUID
    attempt_id: UUID
    lease_token: str
    result_fingerprint: str
    result_summary: str


@dataclass(frozen=True, slots=True)
class FailTaskCommand:
    task_id: UUID
    attempt_id: UUID
    lease_token: str
    failure_category: FailureCategory
    failure_code: str
    result_fingerprint: str
    retry_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AttemptLease:
    """仅供受信任执行器消费的租约，禁止投影到 HTTP、日志或通用状态结果。"""

    attempt_id: UUID
    worker_id: str
    lease_token: str
    lease_expires_at: datetime
    renewal_sequence: int


@dataclass(frozen=True, slots=True)
class ClaimTaskResult:
    task: TaskView
    lease: AttemptLease


@dataclass(frozen=True, slots=True)
class RenewLeaseResult:
    task: TaskView
    lease: AttemptLease
