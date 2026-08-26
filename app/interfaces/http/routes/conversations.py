from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.interfaces.http.assemblers.conversation import (
    conversation_message_page_response,
    conversation_response,
    conversation_summary_page_response,
)
from app.interfaces.http.conversation_cursor import (
    InvalidConversationCursor,
    decode_conversation_cursor,
)
from app.interfaces.http.dependencies import (
    get_conversation_access_service,
    get_conversation_history_read_service,
    get_conversation_list_read_service,
    get_conversation_management_service,
    get_conversation_topic_summary_update_service,
)
from app.interfaces.http.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessagePageResponse,
    ConversationPinRequest,
    ConversationResponse,
    ConversationSummaryPageResponse,
    ConversationSummaryResponse,
    ConversationTopicSummaryUpdateRequest,
)
from app.interfaces.http.security import get_request_principal
from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationDeleteCommand,
    ConversationHistoryReadService,
    ConversationListReadService,
    ConversationManagementService,
    ConversationPinCommand,
    ConversationResolveQuery,
    ConversationTopicSummaryUpdateCommand,
    ConversationTopicSummaryUpdateService,
)
from app.platform.conversation.errors import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    ConversationPinLimitExceededError,
)
from app.platform.conversation.ports import (
    DEFAULT_CONVERSATION_LIST_PAGE_SIZE,
    DEFAULT_HISTORY_PAGE_SIZE,
    DEFAULT_PINNED_CONVERSATION_LIMIT,
    MAX_CONVERSATION_LIST_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
)
from app.platform.security.domain.principal import RequestPrincipal

router = APIRouter()


@router.get(
    "",
    response_model=ConversationSummaryPageResponse,
    responses={403: {"description": "会话列表读取需要可信主体。"}},
)
def list_conversations(
    access: ConversationAccessService = Depends(get_conversation_access_service),
    summaries: ConversationListReadService = Depends(get_conversation_list_read_service),
    principal: RequestPrincipal = Depends(get_request_principal),
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_CONVERSATION_LIST_PAGE_SIZE),
    ] = DEFAULT_CONVERSATION_LIST_PAGE_SIZE,
    cursor: str | None = Query(default=None),
) -> ConversationSummaryPageResponse:
    """Return owner-scoped Conversation summaries without message facts."""

    try:
        owner_subject = access.require_owner_subject(principal)
        list_cursor = decode_conversation_cursor(cursor)
    except (ConversationAccessDeniedError, ConversationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONVERSATION_ACCESS_DENIED",
                "message": "会话不可用。",
            },
        ) from exc
    except InvalidConversationCursor as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CONVERSATION_CURSOR", "message": "分页游标无效。"},
        ) from exc

    page = summaries.list_owned(
        owner_subject=owner_subject,
        limit=limit,
        cursor=list_cursor,
    )
    return conversation_summary_page_response(page)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationResponse,
    responses={403: {"description": "会话创建需要可信主体。"}},
)
def create_conversation(
    request: ConversationCreateRequest = Body(default_factory=ConversationCreateRequest),
    access: ConversationAccessService = Depends(get_conversation_access_service),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> ConversationResponse:
    """Create an empty Conversation owned by the server-resolved principal."""

    del request
    try:
        conversation = access.create(ConversationCreateCommand(principal=principal))
    except (ConversationAccessDeniedError, ConversationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONVERSATION_ACCESS_DENIED",
                "message": "会话不可用。",
            },
        ) from exc
    return conversation_response(conversation)


@router.patch(
    "/{conversation_id}/topic-summary",
    response_model=ConversationSummaryResponse,
    responses={404: {"description": "会话不可用。"}},
)
def update_conversation_topic_summary(
    conversation_id: UUID,
    request: ConversationTopicSummaryUpdateRequest,
    updater: ConversationTopicSummaryUpdateService = Depends(
        get_conversation_topic_summary_update_service
    ),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> ConversationSummaryResponse:
    """Update or clear a topic summary within the current owner's scope."""

    try:
        conversation = updater.update(
            ConversationTopicSummaryUpdateCommand(
                principal=principal,
                conversation_id=conversation_id,
                topic_summary=request.topic_summary,
            )
        )
    except ConversationAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CONVERSATION_UNAVAILABLE",
                "message": "会话不可用。",
            },
        ) from exc
    return ConversationSummaryResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        topic_summary=conversation.topic_summary,
        is_pinned=conversation.is_pinned,
    )


@router.patch(
    "/{conversation_id}/pin",
    response_model=ConversationSummaryResponse,
    responses={
        404: {"description": "会话不可用。"},
        409: {"description": "置顶会话数量已达到上限。"},
    },
)
def update_conversation_pin(
    conversation_id: UUID,
    request: ConversationPinRequest,
    manager: ConversationManagementService = Depends(get_conversation_management_service),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> ConversationSummaryResponse:
    try:
        conversation = manager.pin(
            ConversationPinCommand(
                principal=principal,
                conversation_id=conversation_id,
                is_pinned=request.is_pinned,
            )
        )
    except ConversationAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_UNAVAILABLE", "message": "会话不可用。"},
        ) from exc
    except ConversationPinLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONVERSATION_PIN_LIMIT_REACHED",
                "message": (
                    f"最多置顶 {DEFAULT_PINNED_CONVERSATION_LIMIT} 个会话，请先取消一个。"
                ),
            },
        ) from exc
    return ConversationSummaryResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        topic_summary=conversation.topic_summary,
        is_pinned=conversation.is_pinned,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "会话不可用。"}},
)
def delete_conversation(
    conversation_id: UUID,
    manager: ConversationManagementService = Depends(get_conversation_management_service),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> None:
    try:
        manager.delete(
            ConversationDeleteCommand(principal=principal, conversation_id=conversation_id)
        )
    except ConversationAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_UNAVAILABLE", "message": "会话不可用。"},
        ) from exc


@router.get(
    "/{conversation_id}/messages",
    response_model=ConversationMessagePageResponse,
    responses={404: {"description": "会话不可用。"}},
)
def read_conversation_messages(
    conversation_id: UUID,
    access: ConversationAccessService = Depends(get_conversation_access_service),
    history: ConversationHistoryReadService = Depends(get_conversation_history_read_service),
    principal: RequestPrincipal = Depends(get_request_principal),
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_HISTORY_PAGE_SIZE),
    ] = DEFAULT_HISTORY_PAGE_SIZE,
    after_sequence: Annotated[int | None, Query(gt=0)] = None,
) -> ConversationMessagePageResponse:
    """Return one owner-scoped, ordered, read-only page of Conversation messages."""

    try:
        access.resolve(
            ConversationResolveQuery(
                principal=principal,
                conversation_id=conversation_id,
            )
        )
        page = history.read_history(
            conversation_id=conversation_id,
            limit=limit,
            after_sequence=after_sequence,
        )
    except (ConversationAccessDeniedError, ConversationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "CONVERSATION_UNAVAILABLE",
                "message": "会话不可用。",
            },
        ) from exc
    return conversation_message_page_response(page)
