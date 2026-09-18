"""Task Management 的 PostgreSQL Composition Root。"""

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository
from app.platform.task.application.lifecycle_service import TaskLifecycleService
from app.platform.task.application.trusted_submission import (
    TrustedTaskSubmissionProfile,
    TrustedTaskSubmissionService,
)


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
