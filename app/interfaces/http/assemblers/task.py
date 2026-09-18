from app.interfaces.http.schemas.task import (
    TaskEventPageResponse,
    TaskEventResponse,
    TaskPageResponse,
    TaskResponse,
)
from app.interfaces.http.task_cursor import encode_task_cursor
from app.platform.task.application.contracts import (
    TaskEventListView,
    TaskEventView,
    TaskListView,
    TaskView,
)


def task_response(task: TaskView) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        task_type=task.task_type,
        owner_subject=task.owner_subject,
        status=task.status.value,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        available_at=task.available_at,
        result_summary=task.result_summary,
        failure_code=task.failure_code,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def task_page_response(page: TaskListView) -> TaskPageResponse:
    return TaskPageResponse(
        tasks=[task_response(task) for task in page.tasks],
        has_more=page.has_more,
        next_cursor=encode_task_cursor(page.next_cursor) if page.next_cursor else None,
    )


def task_event_page_response(page: TaskEventListView) -> TaskEventPageResponse:
    return TaskEventPageResponse(
        events=[task_event_response(event) for event in page.events],
        has_more=page.has_more,
        next_after_sequence=page.next_after_sequence,
    )


def task_event_response(event: TaskEventView) -> TaskEventResponse:
    return TaskEventResponse(
        id=event.id,
        sequence=event.sequence,
        transition_id=event.transition_id,
        event_type=event.event_type,
        metadata=dict(event.metadata),
        created_at=event.created_at,
    )
