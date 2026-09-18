"""Task Management 的 PostgreSQL Composition Root。"""

from collections.abc import Mapping
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.task.application.lifecycle_service import TaskLifecycleService
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


def _utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
