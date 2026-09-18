"""Task Management 的 PostgreSQL Composition Root。"""

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.task_repository import PostgresTaskRepository


def build_task_repository(session: Session) -> PostgresTaskRepository:
    """用外部注入的 Session 组装 Task 持久化适配器。"""

    return PostgresTaskRepository(session)
