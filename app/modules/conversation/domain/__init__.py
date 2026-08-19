"""Conversation 领域模型。"""

from app.modules.conversation.domain.conversation import Conversation, ConversationId
from app.modules.conversation.domain.event import ConversationEvent, ConversationEventType
from app.modules.conversation.domain.message import Message, MessageId, MessageRole
from app.modules.conversation.domain.model_context import (
    ContextBudget,
    ContextPolicy,
    ModelContext,
    ModelContextMessage,
)

__all__ = [
    "Conversation",
    "ConversationId",
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
