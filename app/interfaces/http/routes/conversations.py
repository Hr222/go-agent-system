from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.interfaces.http.assemblers.conversation import (
    conversation_message_page_response,
    conversation_response,
)
from app.interfaces.http.dependencies import (
    get_conversation_access_service,
    get_conversation_history_read_service,
)
from app.interfaces.http.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessagePageResponse,
    ConversationResponse,
)
from app.interfaces.http.security import get_request_principal
from app.modules.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationHistoryReadService,
    ConversationResolveQuery,
)
from app.modules.conversation.errors import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
)
from app.modules.conversation.ports import DEFAULT_HISTORY_PAGE_SIZE, MAX_HISTORY_PAGE_SIZE
from app.modules.security.domain.principal import RequestPrincipal

router = APIRouter()


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
    except ConversationAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONVERSATION_ACCESS_DENIED",
                "message": "会话不可用。",
            },
        ) from exc
    return conversation_response(conversation)


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
