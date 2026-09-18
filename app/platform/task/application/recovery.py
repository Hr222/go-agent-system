from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.platform.task.application.contracts import (
    CancelTaskCommand,
    RecoverTaskCommand,
    RequeueTaskCommand,
    RetryTaskCommand,
)
from app.platform.task.application.executor_contracts import ConfirmCancellationCommand
from app.platform.task.application.lifecycle_service import TaskLifecycleService
from app.platform.task.errors import TaskStateTransitionError
from app.platform.task.ports import TaskRepositoryPort


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SchedulingResult:
    task_id: UUID
    status: str | None
    error_code: str | None = None


def _safe_error(exc: Exception) -> str:
    """调度边界只暴露固定分类码，避免底层错误进入日志或返回值。"""

    if isinstance(exc, TaskStateTransitionError):
        return "CANDIDATE_NOT_APPLICABLE"
    return "TASK_SCHEDULING_FAILED"


class RecoveryCoordinator:
    """扫描并恢复过期 lease；每个候选只通过生命周期 Application 转换。"""

    def __init__(
        self,
        repository: TaskRepositoryPort,
        lifecycle: TaskLifecycleService,
        *,
        clock: Callable[[], datetime] = _utc_now,
        retry_delay: timedelta = timedelta(0),
        batch_size: int = 50,
    ) -> None:
        if retry_delay < timedelta(0):
            raise ValueError("恢复退避时间不能为负数。")
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("候选批次大小必须是正整数。")
        self._repository = repository
        self._lifecycle = lifecycle
        self._clock = clock
        self._retry_delay = retry_delay
        self._batch_size = batch_size

    def run_once(self) -> list[SchedulingResult]:
        now = self._clock()
        candidates = self._repository.get_expired_attempts_for_update(
            now=now, limit=self._batch_size
        )
        results: list[SchedulingResult] = []
        for candidate in candidates:
            command_id = (
                f"recover:{candidate.task_id}:{candidate.attempt_id}:"
                f"{candidate.lease_expires_at.isoformat()}"
            )
            retry_at = now + self._retry_delay if self._retry_delay > timedelta(0) else None
            try:
                view = self._lifecycle.recover(
                    RecoverTaskCommand(
                        task_id=candidate.task_id,
                        attempt_id=candidate.attempt_id,
                        command_id=command_id,
                        retry_at=retry_at,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - 隔离单候选，禁止错误跨边界泄漏
                results.append(
                    SchedulingResult(candidate.task_id, None, _safe_error(exc))
                )
            else:
                results.append(SchedulingResult(candidate.task_id, view.status.value))
        return results


class RetryScheduler:
    """只将到期 retry_wait 任务重新入队。"""

    def __init__(
        self,
        repository: TaskRepositoryPort,
        lifecycle: TaskLifecycleService,
        *,
        clock: Callable[[], datetime] = _utc_now,
        batch_size: int = 50,
    ) -> None:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("候选批次大小必须是正整数。")
        self._repository = repository
        self._lifecycle = lifecycle
        self._clock = clock
        self._batch_size = batch_size

    def run_once(self) -> list[SchedulingResult]:
        candidates = self._repository.get_due_retries_for_update(
            now=self._clock(), limit=self._batch_size
        )
        results: list[SchedulingResult] = []
        for candidate in candidates:
            command_id = f"requeue:{candidate.task_id}:{candidate.available_at.isoformat()}"
            try:
                view = self._lifecycle.requeue_due(
                    RequeueTaskCommand(task_id=candidate.task_id, command_id=command_id)
                )
            except Exception as exc:  # noqa: BLE001 - 单候选失败不得阻塞批次
                results.append(SchedulingResult(candidate.task_id, None, _safe_error(exc)))
            else:
                results.append(SchedulingResult(candidate.task_id, view.status.value))
        return results


class CancellationCoordinator:
    """协调请求取消和执行器确认，不强杀线程或外部 Provider。"""

    def __init__(self, lifecycle: TaskLifecycleService) -> None:
        self._lifecycle = lifecycle

    def request(self, *, task_id: UUID, command_id: str) -> SchedulingResult:
        try:
            view = self._lifecycle.cancel(CancelTaskCommand(task_id=task_id, command_id=command_id))
        except Exception as exc:  # noqa: BLE001 - 对外只返回安全分类码
            return SchedulingResult(task_id, None, _safe_error(exc))
        return SchedulingResult(task_id, view.status.value)

    def confirm(self, command: ConfirmCancellationCommand) -> SchedulingResult:
        try:
            view = self._lifecycle.confirm_cancellation(command)
        except Exception as exc:  # noqa: BLE001 - 对外只返回安全分类码
            return SchedulingResult(command.task_id, None, _safe_error(exc))
        return SchedulingResult(command.task_id, view.status.value)


class ManualRetryCoordinator:
    """受信任内部手动重试入口，策略校验仍由 Domain 执行。"""

    def __init__(self, lifecycle: TaskLifecycleService) -> None:
        self._lifecycle = lifecycle

    def retry(self, command: RetryTaskCommand) -> SchedulingResult:
        try:
            view = self._lifecycle.retry(command)
        except Exception as exc:  # noqa: BLE001 - 对外只返回安全分类码
            return SchedulingResult(command.task_id, None, _safe_error(exc))
        return SchedulingResult(command.task_id, view.status.value)


__all__ = [
    "CancellationCoordinator",
    "ManualRetryCoordinator",
    "RecoveryCoordinator",
    "RetryScheduler",
    "SchedulingResult",
]
