"""Task Management 的 PostgreSQL Composition Root。"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.task.application.lifecycle_service import TaskLifecycleService
from app.platform.task.application.recovery import (
    CancellationCoordinator,
    ManualRetryCoordinator,
    RecoveryCoordinator,
    RetryScheduler,
)
from app.platform.task.application.trusted_submission import (
    TrustedTaskSubmissionProfile,
    TrustedTaskSubmissionService,
)
from app.platform.task.application.worker import (
    MappingTaskExecutorRegistry,
    SecureLeaseIssuer,
    TaskWorker,
)
from app.platform.task.ports.worker import LeaseIssuer, TaskExecutor


def build_task_repository(session: Session) -> PostgresTaskRepository:
    """用外部注入的 Session 组装 Task 持久化适配器。"""

    return PostgresTaskRepository(session)


def build_trusted_task_submission_service(
    session: Session,
    profile: TrustedTaskSubmissionProfile,
) -> TrustedTaskSubmissionService:
    """以显式档案组装内部提交能力，不从协议请求读取任务策略。"""

    return TrustedTaskSubmissionService(
        TaskLifecycleService(build_task_repository(session)),
        profile,
    )


def build_task_worker(
    session: Session,
    *,
    worker_id: str,
    executors: Mapping[str, TaskExecutor],
    lease_issuer: LeaseIssuer | None = None,
    clock: Callable[[], datetime] | None = None,
) -> TaskWorker:
    """通过显式 task type 映射组装受信任 Worker，不开放运行时动态注册。"""

    repository = build_task_repository(session)
    lifecycle = TaskLifecycleService(repository, clock=clock or _utc_now)
    return TaskWorker(
        repository=repository,
        lifecycle=lifecycle,
        executors=MappingTaskExecutorRegistry(executors),
        lease_issuer=lease_issuer or SecureLeaseIssuer(),
        worker_id=worker_id,
        clock=clock or _utc_now,
    )


def build_task_recovery_coordinator(
    session: Session,
    *,
    clock: Callable[[], datetime] | None = None,
    retry_delay: timedelta | None = None,
    batch_size: int = 50,
) -> RecoveryCoordinator:
    """组装受信任的 lease 恢复调度器，不暴露协议入口。"""

    repository = build_task_repository(session)
    lifecycle = TaskLifecycleService(repository, clock=clock or _utc_now)
    if retry_delay is None:
        return RecoveryCoordinator(
            repository, lifecycle, clock=clock or _utc_now, batch_size=batch_size
        )
    return RecoveryCoordinator(
        repository,
        lifecycle,
        clock=clock or _utc_now,
        retry_delay=retry_delay,
        batch_size=batch_size,
    )


def build_task_retry_scheduler(
    session: Session,
    *,
    clock: Callable[[], datetime] | None = None,
    batch_size: int = 50,
) -> RetryScheduler:
    """组装退避到期重入队调度器。"""

    repository = build_task_repository(session)
    lifecycle = TaskLifecycleService(repository, clock=clock or _utc_now)
    return RetryScheduler(
        repository, lifecycle, clock=clock or _utc_now, batch_size=batch_size
    )


def build_task_cancellation_coordinator(session: Session) -> CancellationCoordinator:
    """组装协作式取消协调器。"""

    return CancellationCoordinator(TaskLifecycleService(build_task_repository(session)))


def build_task_manual_retry_coordinator(session: Session) -> ManualRetryCoordinator:
    """组装受信任手动重试入口。"""

    return ManualRetryCoordinator(TaskLifecycleService(build_task_repository(session)))


def _utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
