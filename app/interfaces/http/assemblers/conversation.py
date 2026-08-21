from app.interfaces.http.schemas.conversation import (
    ConversationMessagePageResponse,
    ConversationMessageResponse,
    ConversationResponse,
)
from app.modules.conversation.domain import Conversation, Message
from app.modules.conversation.ports import ConversationHistoryPage


def conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
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
