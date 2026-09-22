from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.security.domain.principal import RequestPrincipal
from app.platform.task.domain import TaskStatus
from app.platform.task.errors import TaskAccessDeniedError, TaskResultResourceUnavailableError
from app.platform.task.ports import TaskRepositoryPort
from app.platform.task.ports.result_resource import TaskResultResource, TaskResultResourceReaderPort


@dataclass(frozen=True, slots=True)
class TaskResultResourcesQuery:
    principal: RequestPrincipal
    task_id: UUID


@dataclass(frozen=True, slots=True)
class TaskResultResourcesView:
    task_id: UUID
    conversation_id: str
    resources: tuple[TaskResultResource, ...]


class TaskResultResourceApplication:
    """在 Task owner 和受信任 Conversation 绑定后读取资源清单。"""

    def __init__(self, repository: TaskRepositoryPort, resource_reader: TaskResultResourceReaderPort) -> None:
        self._repository = repository
        self._resource_reader = resource_reader

    def list_owned(self, query: TaskResultResourcesQuery) -> TaskResultResourcesView:
        owner_subject = self._owner_subject(query.principal)
        task = self._repository.get_owned(task_id=query.task_id, owner_subject=owner_subject)
        if task is None or task.status is not TaskStatus.SUCCEEDED:
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        conversation_id = task.display_metadata.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        resources = self._resource_reader.list_resources(task_id=query.task_id, owner_subject=owner_subject, conversation_id=conversation_id.strip())
        if resources is None:
            raise TaskResultResourceUnavailableError("Task 资源不可用。")
        return TaskResultResourcesView(
            task_id=query.task_id,
            conversation_id=conversation_id.strip(),
            resources=resources,
        )

    @staticmethod
    def _owner_subject(principal: RequestPrincipal) -> str:
        if not isinstance(principal, RequestPrincipal) or not principal.authenticated or not isinstance(principal.subject, str) or not principal.subject.strip():
            raise TaskAccessDeniedError("任务管理需要已认证主体。")
        return principal.subject.strip()


__all__ = ["TaskResultResourceApplication", "TaskResultResourcesQuery", "TaskResultResourcesView"]
