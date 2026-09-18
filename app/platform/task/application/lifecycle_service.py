from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from app.platform.task.application.contracts import (
    AttemptLease,
    CancelTaskCommand,
    ClaimTaskCommand,
    ClaimTaskResult,
    CompleteTaskCommand,
    ConfirmCancellationCommand,
    FailTaskCommand,
    RecoverTaskCommand,
    RenewLeaseCommand,
    RenewLeaseResult,
    RequeueTaskCommand,
    RetryTaskCommand,
    SubmitTaskCommand,
    TaskView,
)
from app.platform.task.domain import Task, TaskAttempt
from app.platform.task.errors import (
    TaskIdempotencyConflictError,
    TaskNotFoundError,
)
from app.platform.task.ports import TaskRepositoryPort


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}必须是非空字符串。")
    return value.strip()


class TaskLifecycleService:
    """集中执行 Task 命令幂等，领域对象只承担状态转换。"""

    def __init__(
        self,
        repository: TaskRepositoryPort,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def submit(self, command: SubmitTaskCommand) -> TaskView:
        existing = self._repository.find_by_submission(
            owner_subject=command.owner_subject,
            task_type=command.task_type,
            idempotency_key=command.idempotency_key,
        )
        if existing is not None:
            if existing.input_fingerprint != command.input_fingerprint:
                raise TaskIdempotencyConflictError("同一幂等键使用了不同的输入指纹。")
            return TaskView.from_task(existing)
        task = Task.create(
            task_type=command.task_type,
            owner_subject=command.owner_subject,
            idempotency_key=command.idempotency_key,
            input_fingerprint=command.input_fingerprint,
            max_attempts=command.max_attempts,
            display_metadata=command.display_metadata,
            allow_manual_retry=command.allow_manual_retry,
            now=self._clock(),
        )
        self._repository.save(task)
        return TaskView.from_task(task)

    def claim(self, command: ClaimTaskCommand) -> ClaimTaskResult:
        task = self._task(command.task_id)
        existing = task.find_attempt_by_claim(
            worker_id=command.worker_id,
            claim_id=command.claim_id,
        )
        if existing is not None:
            if existing.lease_token != _require_text(command.lease_token, "租约令牌"):
                raise TaskIdempotencyConflictError("同一领取标识使用了不同的租约令牌。")
            return ClaimTaskResult(task=TaskView.from_task(task), lease=self._lease(existing))
        attempt = task.claim(
            worker_id=command.worker_id,
            claim_id=command.claim_id,
            lease_token=command.lease_token,
            lease_expires_at=command.lease_expires_at,
            now=self._clock(),
        )
        self._repository.save(task)
        return ClaimTaskResult(task=TaskView.from_task(task), lease=self._lease(attempt))

    def renew_lease(self, command: RenewLeaseCommand) -> RenewLeaseResult:
        task = self._task(command.task_id)
        attempt = task.renew_lease(
            attempt_id=command.attempt_id,
            lease_token=command.lease_token,
            renewal_sequence=command.renewal_sequence,
            lease_expires_at=command.lease_expires_at,
            now=self._clock(),
        )
        self._repository.save(task)
        return RenewLeaseResult(task=TaskView.from_task(task), lease=self._lease(attempt))

    def cancel(self, command: CancelTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        if self._already_processed(task.id, "cancel", command.command_id):
            return TaskView.from_task(task)
        task.request_cancel(command_id=command.command_id, now=self._clock())
        self._record_processed(task.id, "cancel", command.command_id)
        self._repository.save(task)
        return TaskView.from_task(task)

    def confirm_cancellation(self, command: ConfirmCancellationCommand) -> TaskView:
        task = self._task(command.task_id)
        task.confirm_cancel(
            attempt_id=command.attempt_id,
            lease_token=command.lease_token,
            now=self._clock(),
        )
        self._repository.save(task)
        return TaskView.from_task(task)

    def complete(self, command: CompleteTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        task.complete(
            attempt_id=command.attempt_id,
            lease_token=command.lease_token,
            result_fingerprint=command.result_fingerprint,
            result_summary=command.result_summary,
            now=self._clock(),
        )
        self._repository.save(task)
        return TaskView.from_task(task)

    def fail(self, command: FailTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        task.fail(
            attempt_id=command.attempt_id,
            lease_token=command.lease_token,
            failure_category=command.failure_category,
            failure_code=command.failure_code,
            result_fingerprint=command.result_fingerprint,
            retry_at=command.retry_at,
            now=self._clock(),
        )
        self._repository.save(task)
        return TaskView.from_task(task)

    def requeue_due(self, command: RequeueTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        if self._already_processed(task.id, "requeue", command.command_id):
            return TaskView.from_task(task)
        task.requeue_due(command_id=command.command_id, now=self._clock())
        self._record_processed(task.id, "requeue", command.command_id)
        self._repository.save(task)
        return TaskView.from_task(task)

    def retry(self, command: RetryTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        if self._already_processed(task.id, "manual-retry", command.command_id):
            return TaskView.from_task(task)
        task.request_manual_retry(command_id=command.command_id, now=self._clock())
        self._record_processed(task.id, "manual-retry", command.command_id)
        self._repository.save(task)
        return TaskView.from_task(task)

    def recover(self, command: RecoverTaskCommand) -> TaskView:
        task = self._task(command.task_id)
        if self._already_processed(task.id, "recover", command.command_id):
            return TaskView.from_task(task)
        task.recover_expired_attempt(
            command_id=command.command_id,
            retry_at=command.retry_at,
            now=self._clock(),
        )
        self._record_processed(task.id, "recover", command.command_id)
        self._repository.save(task)
        return TaskView.from_task(task)

    def _task(self, task_id: UUID) -> Task:
        if not isinstance(task_id, UUID):
            raise ValueError("任务标识必须是 UUID。")
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError("任务不存在。")
        return task

    def _already_processed(self, task_id: UUID, command_type: str, command_id: str) -> bool:
        return self._repository.has_processed_command(
            task_id=task_id,
            command_type=command_type,
            command_id=_require_text(command_id, "命令标识"),
        )

    def _record_processed(self, task_id: UUID, command_type: str, command_id: str) -> None:
        self._repository.mark_command_processed(
            task_id=task_id,
            command_type=command_type,
            command_id=_require_text(command_id, "命令标识"),
        )

    @staticmethod
    def _lease(attempt: TaskAttempt) -> AttemptLease:
        return AttemptLease(
            attempt_id=attempt.id,
            worker_id=attempt.worker_id,
            lease_token=attempt.lease_token,
            lease_expires_at=attempt.lease_expires_at,
            renewal_sequence=attempt.renewal_sequence,
        )
