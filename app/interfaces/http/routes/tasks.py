from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.interfaces.http.assemblers.task import (
    task_event_page_response,
    task_page_response,
    task_response,
)
from app.interfaces.http.dependencies import (
    get_owned_task_application,
    get_task_result_resource_application,
)
from app.interfaces.http.schemas.task import (
    TaskCommandRequest,
    TaskEventPageResponse,
    TaskPageResponse,
    TaskResponse,
    TaskResultResourceListResponse,
    TaskResultResourceResponse,
)
from app.interfaces.http.security import get_request_principal
from app.interfaces.http.task_cursor import InvalidTaskCursor, decode_task_cursor
from app.platform.security.domain.principal import RequestPrincipal
from app.platform.task.application import (
    OwnedTaskApplication,
    OwnedTaskCommand,
    OwnedTaskEventsQuery,
    OwnedTaskListQuery,
    OwnedTaskQuery,
    TaskResultResourceApplication,
    TaskResultResourcesQuery,
)
from app.platform.task.errors import (
    TaskAccessDeniedError,
    TaskResultResourceUnavailableError,
    TaskUnavailableError,
)
from app.shared.config import settings

router = APIRouter()
DEFAULT_TASK_PAGE_SIZE = 50
MAX_TASK_PAGE_SIZE = 200
DEFAULT_TASK_EVENT_PAGE_SIZE = 50
MAX_TASK_EVENT_PAGE_SIZE = 200


def _validate_page_limit(limit: int, maximum: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_TASK_PAGINATION", "message": "任务分页参数无效。"},
        )
    return limit


def _validate_after_sequence(after_sequence: int | None) -> int | None:
    if after_sequence is not None and (
        isinstance(after_sequence, bool)
        or not isinstance(after_sequence, int)
        or after_sequence <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_TASK_PAGINATION", "message": "任务分页参数无效。"},
        )
    return after_sequence


def _access_denied(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "TASK_ACCESS_DENIED", "message": "任务管理需要已认证主体。"},
    )


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "TASK_UNAVAILABLE", "message": "任务不可用。"},
    )


def _resources_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "TASK_RESOURCES_UNAVAILABLE", "message": "任务结果资源不可用。"},
    )


def _command_error(code: str) -> HTTPException:
    if code == "CANDIDATE_NOT_APPLICABLE":
        status_code = status.HTTP_409_CONFLICT
        public_code = "TASK_COMMAND_REJECTED"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        public_code = "TASK_COMMAND_FAILED"
    return HTTPException(
        status_code=status_code,
        detail={"code": public_code, "message": "任务命令未完成。"},
    )


@router.get("", response_model=TaskPageResponse)
def list_tasks(
    application: OwnedTaskApplication = Depends(get_owned_task_application),
    principal: RequestPrincipal = Depends(get_request_principal),
    limit: Annotated[int, Query()] = DEFAULT_TASK_PAGE_SIZE,
    cursor: str | None = Query(default=None),
) -> TaskPageResponse:
    try:
        limit = _validate_page_limit(limit, MAX_TASK_PAGE_SIZE)
        page_cursor = decode_task_cursor(cursor)
        page = application.list_owned(
            OwnedTaskListQuery(principal=principal, limit=limit, cursor=page_cursor)
        )
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except InvalidTaskCursor as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_TASK_PAGINATION", "message": "任务分页参数无效。"},
        ) from exc
    return task_page_response(page)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    application: OwnedTaskApplication = Depends(get_owned_task_application),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> TaskResponse:
    try:
        task = application.get_owned(OwnedTaskQuery(principal=principal, task_id=task_id))
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except TaskUnavailableError as exc:
        raise _unavailable(exc) from exc
    return task_response(task)


@router.get(
    "/{task_id}/resources",
    response_model=TaskResultResourceListResponse,
    responses={404: {"description": "任务结果资源不可用。"}},
)
def get_task_result_resources(
    task_id: UUID,
    conversation_id: UUID,
    application: TaskResultResourceApplication = Depends(
        get_task_result_resource_application
    ),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> TaskResultResourceListResponse:
    """返回已完成 Task 的安全资源清单，文件仍走受控附件下载。"""

    try:
        result = application.list_owned(
            TaskResultResourcesQuery(
                principal=principal,
                task_id=task_id,
                conversation_id=str(conversation_id),
            )
        )
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except TaskResultResourceUnavailableError as exc:
        raise _resources_unavailable(exc) from exc
    return TaskResultResourceListResponse(
        task_id=result.task_id,
        resources=[
            TaskResultResourceResponse(
                resource_id=resource.resource_id,
                file_name=resource.file_name,
                media_type=resource.media_type,
                size_bytes=resource.size_bytes,
                sha256=resource.sha256,
                download_url=(
                    f"{settings.api_v1_prefix}/attachments/{resource.resource_id}/download"
                    f"?conversation_id={conversation_id}"
                ),
            )
            for resource in result.resources
        ],
    )


@router.get("/{task_id}/events", response_model=TaskEventPageResponse)
def get_task_events(
    task_id: UUID,
    application: OwnedTaskApplication = Depends(get_owned_task_application),
    principal: RequestPrincipal = Depends(get_request_principal),
    limit: Annotated[int, Query()] = DEFAULT_TASK_EVENT_PAGE_SIZE,
    after_sequence: Annotated[int | None, Query()] = None,
) -> TaskEventPageResponse:
    try:
        limit = _validate_page_limit(limit, MAX_TASK_EVENT_PAGE_SIZE)
        after_sequence = _validate_after_sequence(after_sequence)
        page = application.read_events(
            OwnedTaskEventsQuery(
                principal=principal,
                task_id=task_id,
                limit=limit,
                after_sequence=after_sequence,
            )
        )
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except TaskUnavailableError as exc:
        raise _unavailable(exc) from exc
    return task_event_page_response(page)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(
    task_id: UUID,
    request: TaskCommandRequest,
    application: OwnedTaskApplication = Depends(get_owned_task_application),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> TaskResponse:
    try:
        result = application.cancel(
            OwnedTaskCommand(
                principal=principal,
                task_id=task_id,
                command_id=request.command_id,
            )
        )
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except TaskUnavailableError as exc:
        raise _unavailable(exc) from exc
    if result.error_code is not None:
        raise _command_error(result.error_code)
    assert result.task is not None
    return task_response(result.task)


@router.post("/{task_id}/retry", response_model=TaskResponse)
def retry_task(
    task_id: UUID,
    request: TaskCommandRequest,
    application: OwnedTaskApplication = Depends(get_owned_task_application),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> TaskResponse:
    try:
        result = application.retry(
            OwnedTaskCommand(
                principal=principal,
                task_id=task_id,
                command_id=request.command_id,
            )
        )
    except TaskAccessDeniedError as exc:
        raise _access_denied(exc) from exc
    except TaskUnavailableError as exc:
        raise _unavailable(exc) from exc
    if result.error_code is not None:
        raise _command_error(result.error_code)
    assert result.task is not None
    return task_response(result.task)
