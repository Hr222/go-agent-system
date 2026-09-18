from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Mapping, Protocol, TypeAlias
from uuid import UUID

from app.platform.task.domain import FailureCategory

if TYPE_CHECKING:
    from app.platform.task.application.executor_contracts import AttemptLease


@dataclass(frozen=True, slots=True)
class LeaseGrant:
    """Worker 在领取前生成的内部租约材料。"""

    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class TaskExecutionContext:
    """执行器可见的最小安全上下文；不包含输入指纹或原始输入。"""

    task_id: UUID
    task_type: str
    display_metadata: Mapping[str, str]
    lease: AttemptLease
    renew_lease: Callable[[], object]


@dataclass(frozen=True, slots=True)
class TaskExecutionSuccess:
    result_fingerprint: str
    result_summary: str


@dataclass(frozen=True, slots=True)
class TaskExecutionFailure:
    failure_category: FailureCategory
    failure_code: str
    result_fingerprint: str
    retry_at: datetime | None = None


TaskExecutionOutcome: TypeAlias = TaskExecutionSuccess | TaskExecutionFailure


class TaskExecutor(Protocol):
    """受 Composition Root 固定绑定的任务执行器。"""

    def execute(self, context: TaskExecutionContext) -> TaskExecutionOutcome: ...


class TaskExecutorRegistry(Protocol):
    """服务端 task type 到执行器的固定查找边界。"""

    def resolve(self, task_type: str) -> TaskExecutor | None: ...


class LeaseIssuer(Protocol):
    """只在受信任 Worker 内签发 lease。"""

    def issue(self, *, worker_id: str, now: datetime) -> LeaseGrant: ...

    def renew(
        self,
        *,
        worker_id: str,
        now: datetime,
        current_expires_at: datetime,
    ) -> datetime: ...


__all__ = [
    "LeaseGrant",
    "LeaseIssuer",
    "TaskExecutionContext",
    "TaskExecutionFailure",
    "TaskExecutionOutcome",
    "TaskExecutionSuccess",
    "TaskExecutor",
    "TaskExecutorRegistry",
]
