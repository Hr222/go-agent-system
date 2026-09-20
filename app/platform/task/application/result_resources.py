from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.security.domain.principal import RequestPrincipal
from app.platform.task.domain import TaskStatus
from app.platform.task.errors import (
    TaskAccessDeniedError,
    TaskResultResourceUnavailableError,
)
from app.platform.task.ports import TaskRepositoryPort, TaskResultResourceReaderPort
from app.platform.task.ports.result_resource import TaskResultResource


@dataclass(frozen=True, slots=True)
class TaskResultResourcesQuery:
    principal: RequestPrincipal
    task_id: UUID
    conversation_id: str


@dataclass(frozen=True, slots=True)
class TaskResultResourcesView:
    task_id: UUID
    resources: tuple[TaskResultResource, ...]


class TaskResultResourceApplication:
    """主体和 Conversation 双重校验后的 Task 结果资源查询用例。"""

    def __init__(
        self,
        repository: TaskRepositoryPort,
        resource_reader: TaskResultResourceReaderPort,
    ) -> None:
        self._repository = repository
        self._resource_reader = resource_reader

    def list_owned(self, query: TaskResultResourcesQuery) -> TaskResultResourcesView:
        owner_subject = self._owner_subject(query.principal)
        if not isinstance(query.conversation_id, str) or not query.conversation_id.strip():
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        task = self._repository.get_owned(
            task_id=query.task_id,
            owner_subject=owner_subject,
        )
        if task is None or task.status is not TaskStatus.SUCCEEDED:
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        if task.display_metadata.get("conversation_id") != query.conversation_id.strip():
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        resources = self._resource_reader.list_resources(
            task_id=query.task_id,
            owner_subject=owner_subject,
            conversation_id=query.conversation_id.strip(),
        )
        if resources is None:
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        return TaskResultResourcesView(task_id=query.task_id, resources=resources)

    @staticmethod
    def _owner_subject(principal: RequestPrincipal) -> str:
        if (
            not isinstance(principal, RequestPrincipal)
            or not principal.authenticated
            or not isinstance(principal.subject, str)
            or not principal.subject.strip()
        ):
            raise TaskAccessDeniedError("任务管理需要已认证主体。")
        return principal.subject.strip()


__all__ = [
    "TaskResultResource",
    "TaskResultResourceApplication",
    "TaskResultResourceReaderPort",
    "TaskResultResourcesQuery",
    "TaskResultResourcesView",
]
