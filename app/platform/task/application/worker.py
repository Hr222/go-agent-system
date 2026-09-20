from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Callable, Mapping
from uuid import UUID, uuid4

from app.platform.task.application.contracts import CancellationCheckCommand, TaskView
from app.platform.task.application.executor_contracts import (
    ClaimTaskCommand,
    CompleteTaskCommand,
    ConfirmCancellationCommand,
    FailTaskCommand,
    RenewLeaseCommand,
)
from app.platform.task.application.lifecycle_service import TaskLifecycleService
from app.platform.task.domain import FailureCategory
from app.platform.task.errors import TaskLeaseRejectedError
from app.platform.task.ports import TaskRepositoryPort
from app.platform.task.ports.worker import (
    LeaseGrant,
    LeaseIssuer,
    TaskExecutionCancellation,
    TaskExecutionContext,
    TaskExecutionFailure,
    TaskExecutionSuccess,
    TaskExecutor,
    TaskExecutorRegistry,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SecureLeaseIssuer:
    """生成不可预测且具有固定有效期的内部 lease。"""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=5),
        token_factory: Callable[[], str] = secrets.token_urlsafe,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("租约有效期必须为正数。")
        self._ttl = ttl
        self._token_factory = token_factory

    def issue(self, *, worker_id: str, now: datetime) -> LeaseGrant:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("执行者标识必须是非空字符串。")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("当前时间必须带时区。")
        token = self._token_factory()
        if not isinstance(token, str) or not token.strip():
            raise ValueError("租约签发器返回了无效令牌。")
        return LeaseGrant(
            lease_token=token,
            lease_expires_at=now.astimezone(timezone.utc) + self._ttl,
        )

    def renew(
        self,
        *,
        worker_id: str,
        now: datetime,
        current_expires_at: datetime,
    ) -> datetime:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("执行者标识必须是非空字符串。")
        normalized_now = now.astimezone(timezone.utc)
        normalized_current = current_expires_at.astimezone(timezone.utc)
        renewed = max(normalized_now, normalized_current) + self._ttl
        if renewed <= normalized_current:
            raise ValueError("续租到期时间必须晚于当前到期时间。")
        return renewed


class MappingTaskExecutorRegistry:
    """只保存 Composition Root 提供的显式 task type 绑定。"""

    def __init__(self, executors: Mapping[str, TaskExecutor]) -> None:
        self._executors = dict(executors)

    def resolve(self, task_type: str) -> TaskExecutor | None:
        return self._executors.get(task_type)


class WorkerPollStatus(StrEnum):
    IDLE = "idle"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class WorkerPollResult:
    status: WorkerPollStatus
    task: TaskView | None = None
    error_code: str | None = None


class TaskWorker:
    """一次只执行一个 Task 的受信任 Worker。"""

    def __init__(
        self,
        *,
        repository: TaskRepositoryPort,
        lifecycle: TaskLifecycleService,
        executors: TaskExecutorRegistry,
        lease_issuer: LeaseIssuer,
        worker_id: str,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("执行者标识必须是非空字符串。")
        self._repository = repository
        self._lifecycle = lifecycle
        self._executors = executors
        self._lease_issuer = lease_issuer
        self._worker_id = worker_id.strip()
        self._clock = clock

    def poll_once(self) -> WorkerPollResult:
        now = self._clock()
        candidate = self._repository.get_next_queued_for_update(now=now)
        if candidate is None:
            return WorkerPollResult(status=WorkerPollStatus.IDLE)

        try:
            lease = self._lease_issuer.issue(worker_id=self._worker_id, now=now)
            claim_id = str(uuid4())
            claimed = self._lifecycle.claim(
                ClaimTaskCommand(
                    task_id=candidate.id,
                    worker_id=self._worker_id,
                    claim_id=claim_id,
                    lease_token=lease.lease_token,
                    lease_expires_at=lease.lease_expires_at,
                )
            )
        except Exception:
            self._release_claim_slot()
            raise

        executor = self._executors.resolve(candidate.task_type)
        if executor is None:
            return self._finish_failure(
                claimed.task.id,
                claimed.lease.attempt_id,
                claimed.lease.lease_token,
                TaskExecutionFailure(
                    failure_category=FailureCategory.PERMANENT,
                    failure_code="EXECUTOR_UNAVAILABLE",
                    result_fingerprint="executor-unavailable",
                ),
            )

        context = TaskExecutionContext(
            task_id=candidate.id,
            task_type=candidate.task_type,
            owner_subject=candidate.owner_subject,
            display_metadata=dict(candidate.display_metadata),
            lease=claimed.lease,
            renew_lease=self._renew_callback(
                task_id=claimed.task.id,
                attempt_id=claimed.lease.attempt_id,
                lease_token=claimed.lease.lease_token,
                worker_id=claimed.lease.worker_id,
                current_expires_at=claimed.lease.lease_expires_at,
            ),
            is_cancel_requested=lambda: self._lifecycle.is_cancel_requested(
                CancellationCheckCommand(
                    task_id=claimed.task.id,
                    attempt_id=claimed.lease.attempt_id,
                    lease_token=claimed.lease.lease_token,
                )
            ),
        )
        try:
            outcome = executor.execute(context)
        except TaskLeaseRejectedError:
            return WorkerPollResult(
                status=WorkerPollStatus.REJECTED,
                task=None,
                error_code="LEASE_REJECTED",
            )
        except Exception:  # noqa: BLE001 - 不跨越 Worker 边界泄漏执行器内部异常
            outcome = TaskExecutionFailure(
                failure_category=FailureCategory.PERMANENT,
                failure_code="EXECUTOR_FAILED",
                result_fingerprint="executor-failed",
            )
        if not isinstance(
            outcome,
            (TaskExecutionSuccess, TaskExecutionFailure, TaskExecutionCancellation),
        ):
            outcome = TaskExecutionFailure(
                failure_category=FailureCategory.PERMANENT,
                failure_code="INVALID_EXECUTOR_RESULT",
                result_fingerprint="invalid-executor-result",
            )
        elif (
            isinstance(outcome, TaskExecutionFailure)
            and outcome.failure_category is FailureCategory.TRANSIENT
            and outcome.retry_at is None
        ):
            outcome = TaskExecutionFailure(
                failure_category=FailureCategory.PERMANENT,
                failure_code="INVALID_RETRY_SCHEDULE",
                result_fingerprint="invalid-retry-schedule",
            )

        if isinstance(outcome, TaskExecutionCancellation):
            try:
                task = self._lifecycle.confirm_cancellation(
                    ConfirmCancellationCommand(
                        task_id=claimed.task.id,
                        attempt_id=claimed.lease.attempt_id,
                        lease_token=claimed.lease.lease_token,
                    )
                )
            except Exception:
                return WorkerPollResult(
                    status=WorkerPollStatus.REJECTED,
                    task=None,
                    error_code="CANCELLATION_COMMIT_REJECTED",
                )
            return WorkerPollResult(status=WorkerPollStatus.CANCELLED, task=task)

        if isinstance(outcome, TaskExecutionSuccess):
            try:
                task = self._lifecycle.complete(
                    CompleteTaskCommand(
                        task_id=claimed.task.id,
                        attempt_id=claimed.lease.attempt_id,
                        lease_token=claimed.lease.lease_token,
                        result_fingerprint=outcome.result_fingerprint,
                        result_summary=outcome.result_summary,
                    )
                )
            except Exception:
                return WorkerPollResult(
                    status=WorkerPollStatus.REJECTED,
                    task=None,
                    error_code="RESULT_COMMIT_REJECTED",
                )
            return WorkerPollResult(status=WorkerPollStatus.SUCCEEDED, task=task)

        return self._finish_failure(
            claimed.task.id,
            claimed.lease.attempt_id,
            claimed.lease.lease_token,
            outcome,
        )

    def _finish_failure(
        self,
        task_id: UUID,
        attempt_id: UUID,
        lease_token: str,
        outcome: TaskExecutionFailure,
    ) -> WorkerPollResult:
        try:
            task = self._lifecycle.fail(
                FailTaskCommand(
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_token=lease_token,
                    failure_category=outcome.failure_category,
                    failure_code=outcome.failure_code,
                    result_fingerprint=outcome.result_fingerprint,
                    retry_at=outcome.retry_at,
                )
            )
        except Exception:
            return WorkerPollResult(
                status=WorkerPollStatus.REJECTED,
                task=None,
                error_code="FAILURE_COMMIT_REJECTED",
            )
        return WorkerPollResult(status=WorkerPollStatus.FAILED, task=task)

    def _renew_callback(
        self,
        *,
        task_id: UUID,
        attempt_id: UUID,
        lease_token: str,
        worker_id: str,
        current_expires_at: datetime,
    ) -> Callable[[], object]:
        renewal_sequence = 0
        expires_at = current_expires_at

        def renew() -> object:
            nonlocal renewal_sequence, expires_at
            now = self._clock()
            next_expires_at = self._lease_issuer.renew(
                worker_id=worker_id,
                now=now,
                current_expires_at=expires_at,
            )
            renewal_sequence += 1
            result = self._lifecycle.renew_lease(
                RenewLeaseCommand(
                    task_id=task_id,
                    attempt_id=attempt_id,
                    lease_token=lease_token,
                    renewal_sequence=renewal_sequence,
                    lease_expires_at=next_expires_at,
                )
            )
            expires_at = result.lease.lease_expires_at
            return result.lease

        return renew

    def _release_claim_slot(self) -> None:
        release = getattr(self._repository, "release_claim_slot", None)
        if release is not None:
            release()


__all__ = [
    "MappingTaskExecutorRegistry",
    "SecureLeaseIssuer",
    "TaskWorker",
    "WorkerPollResult",
    "WorkerPollStatus",
]
