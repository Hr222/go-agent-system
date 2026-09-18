from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.security.domain.principal import RequestPrincipal
from app.platform.task.application.contracts import (
    RetryTaskCommand,
    TaskEventListView,
    TaskEventView,
    TaskListView,
    TaskView,
)
from app.platform.task.application.recovery import (
    CancellationCoordinator,
    ManualRetryCoordinator,
)
from app.platform.task.errors import (
    TaskAccessDeniedError,
    TaskUnavailableError,
)
from app.platform.task.ports import TaskListCursor, TaskRepositoryPort


@dataclass(frozen=True, slots=True)
class OwnedTaskListQuery:
    principal: RequestPrincipal
    limit: int
    cursor: TaskListCursor | None = None


@dataclass(frozen=True, slots=True)
class OwnedTaskQuery:
    principal: RequestPrincipal
    task_id: UUID


@dataclass(frozen=True, slots=True)
class OwnedTaskEventsQuery:
    principal: RequestPrincipal
    task_id: UUID
    limit: int
    after_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class OwnedTaskCommand:
    principal: RequestPrincipal
    task_id: UUID
    command_id: str


@dataclass(frozen=True, slots=True)
class OwnedTaskCommandResult:
    task: TaskView | None
    error_code: str | None = None


class OwnedTaskApplication:
    """主体范围 Task HTTP 用例；协议层不能绕过此 admission 边界。"""

    def __init__(
        self,
        repository: TaskRepositoryPort,
        cancellation: CancellationCoordinator,
        manual_retry: ManualRetryCoordinator,
    ) -> None:
        self._repository = repository
        self._cancellation = cancellation
        self._manual_retry = manual_retry

    def list_owned(self, query: OwnedTaskListQuery) -> TaskListView:
        owner_subject = self._owner_subject(query.principal)
        page = self._repository.list_owned(
            owner_subject=owner_subject,
            limit=query.limit,
            cursor=query.cursor,
        )
        return TaskListView(
            tasks=tuple(TaskView.from_task(task) for task in page.tasks),
            has_more=page.has_more,
            next_cursor=page.next_cursor,
        )

    def get_owned(self, query: OwnedTaskQuery) -> TaskView:
        task = self._repository.get_owned(
            task_id=query.task_id,
            owner_subject=self._owner_subject(query.principal),
        )
        if task is None:
            raise TaskUnavailableError("任务不可用。")
        return TaskView.from_task(task)

    def read_events(self, query: OwnedTaskEventsQuery) -> TaskEventListView:
        page = self._repository.read_owned_events(
            task_id=query.task_id,
            owner_subject=self._owner_subject(query.principal),
            limit=query.limit,
            after_sequence=query.after_sequence,
        )
        if page is None:
            raise TaskUnavailableError("任务不可用。")
        return TaskEventListView(
            events=tuple(
                TaskEventView(
                    id=event.id,
                    sequence=event.sequence,
                    transition_id=event.transition_id,
                    event_type=event.event_type.value,
                    metadata=dict(event.metadata),
                    created_at=event.created_at,
                )
                for event in page.events
            ),
            has_more=page.has_more,
            next_after_sequence=page.next_after_sequence,
        )

    def cancel(self, command: OwnedTaskCommand) -> OwnedTaskCommandResult:
        self._require_owned(command)
        result = self._cancellation.request(
            task_id=command.task_id,
            command_id=command.command_id,
        )
        return self._command_result(command, result.error_code)

    def retry(self, command: OwnedTaskCommand) -> OwnedTaskCommandResult:
        self._require_owned(command)
        result = self._manual_retry.retry(
            RetryTaskCommand(task_id=command.task_id, command_id=command.command_id)
        )
        return self._command_result(command, result.error_code)

    def _require_owned(self, command: OwnedTaskCommand) -> None:
        if self._repository.get_owned(
            task_id=command.task_id,
            owner_subject=self._owner_subject(command.principal),
        ) is None:
            raise TaskUnavailableError("任务不可用。")

    def _command_result(
        self, command: OwnedTaskCommand, error_code: str | None
    ) -> OwnedTaskCommandResult:
        if error_code is not None:
            return OwnedTaskCommandResult(task=None, error_code=error_code)
        task = self._repository.get_owned(
            task_id=command.task_id,
            owner_subject=self._owner_subject(command.principal),
        )
        if task is None:
            raise TaskUnavailableError("任务不可用。")
        return OwnedTaskCommandResult(task=TaskView.from_task(task))

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
    "OwnedTaskApplication",
    "OwnedTaskCommand",
    "OwnedTaskCommandResult",
    "OwnedTaskEventsQuery",
    "OwnedTaskListQuery",
    "OwnedTaskQuery",
]
