"""Conversation 领域模型。"""

from app.platform.conversation.domain.conversation import (
    MAX_TOPIC_SUMMARY_LENGTH,
    Conversation,
    ConversationId,
)
from app.platform.conversation.domain.event import ConversationEvent, ConversationEventType
from app.platform.conversation.domain.message import Message, MessageId, MessageRole
from app.platform.conversation.domain.model_context import (
    ContextBudget,
    ContextPolicy,
    ModelContext,
    ModelContextMessage,
)

__all__ = [
    "Conversation",
    "ConversationId",
    "MAX_TOPIC_SUMMARY_LENGTH",
    "ConversationEvent",
    "ConversationEventType",
    "ContextBudget",
    "ContextPolicy",
    "Message",
    "MessageId",
    "MessageRole",
    "ModelContext",
    "ModelContextMessage",
]
