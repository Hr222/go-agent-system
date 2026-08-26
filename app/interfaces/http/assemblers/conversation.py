from app.interfaces.http.conversation_cursor import encode_conversation_cursor
from app.interfaces.http.schemas.conversation import (
    ConversationMessagePageResponse,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationSummaryPageResponse,
    ConversationSummaryResponse,
)
from app.platform.conversation.domain import Conversation, Message
from app.platform.conversation.ports import (
    ConversationHistoryPage,
    ConversationSummary,
    ConversationSummaryPage,
)


def conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        topic_summary=conversation.topic_summary,
        is_pinned=conversation.is_pinned,
    )


def conversation_message_page_response(
    page: ConversationHistoryPage,
) -> ConversationMessagePageResponse:
    return ConversationMessagePageResponse(
        conversation=conversation_response(page.conversation),
        messages=[_message_response(message) for message in page.messages],
        has_more=page.has_more,
        next_after_sequence=page.next_after_sequence,
    )


def _message_response(message: Message) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=message.id,
        role=message.role.value,
        content=message.content,
        sequence=message.sequence,
        created_at=message.created_at,
    )


def conversation_summary_page_response(
    page: ConversationSummaryPage,
) -> ConversationSummaryPageResponse:
    return ConversationSummaryPageResponse(
        conversations=[conversation_summary_response(item) for item in page.conversations],
        has_more=page.has_more,
        next_cursor=(
            encode_conversation_cursor(page.next_cursor)
            if page.next_cursor is not None
            else None
        ),
    )


def conversation_summary_response(
    summary: ConversationSummary,
) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=summary.id,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        topic_summary=summary.topic_summary,
        is_pinned=summary.is_pinned,
    )
