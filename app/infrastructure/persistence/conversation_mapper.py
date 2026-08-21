from __future__ import annotations

from app.infrastructure.persistence.models.conversation import (
    ConversationEventRecord,
    ConversationMessageRecord,
    ConversationRecord,
)
from app.modules.conversation.domain import Conversation, ConversationEvent, Message, MessageRole


def conversation_to_record(conversation: Conversation) -> ConversationRecord:
    """将领域会话转换为可持久化记录，不将 ORM 类型泄漏到领域层。"""

    return ConversationRecord(
        id=conversation.id,
        owner_subject=conversation.owner_subject,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def conversation_from_record(record: ConversationRecord) -> Conversation:
    """从已持久化记录恢复领域会话。"""

    return Conversation(
        id=record.id,
        owner_subject=record.owner_subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def message_to_record(message: Message) -> ConversationMessageRecord:
    """将领域消息转换为可持久化记录。"""

    return ConversationMessageRecord(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        sequence=message.sequence,
        created_at=message.created_at,
    )


def message_from_record(record: ConversationMessageRecord) -> Message:
    """从已持久化记录恢复领域消息。"""

    return Message(
        id=record.id,
        conversation_id=record.conversation_id,
        role=MessageRole(record.role),
        content=record.content,
        sequence=record.sequence,
        created_at=record.created_at,
    )


def event_to_record(event: ConversationEvent) -> ConversationEventRecord:
    return ConversationEventRecord(
        id=event.id,
        conversation_id=event.conversation_id,
        event_type=event.event_type,
        call_id=event.call_id,
        capability_code=event.capability_code,
        sequence=event.sequence,
        payload=dict(event.payload),
        created_at=event.created_at,
    )


def event_from_record(record: ConversationEventRecord) -> ConversationEvent:
    return ConversationEvent(
        id=record.id,
        conversation_id=record.conversation_id,
        event_type=record.event_type,
        call_id=record.call_id,
        capability_code=record.capability_code,
        sequence=record.sequence,
        payload=dict(record.payload),
        created_at=record.created_at,
    )
