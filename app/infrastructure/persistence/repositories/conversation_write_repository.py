from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.conversation_mapper import (
    conversation_from_record,
    conversation_to_record,
    message_from_record,
    message_to_record,
)
from app.infrastructure.persistence.models.conversation import (
    ConversationMessageRecord,
    ConversationRecord,
)
from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.conversation.errors import ConversationNotFoundError
from app.modules.conversation.ports.write_port import ConversationWritePort


class ConversationWriteRepository(ConversationWritePort):
    """Conversation 写入 PostgreSQL 适配器。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_conversation(self, conversation: Conversation) -> Conversation:
        record = conversation_to_record(conversation)
        try:
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return conversation_from_record(record)
        except Exception:
            self.session.rollback()
            raise

    def update_topic_summary(
        self,
        *,
        conversation_id: UUID,
        topic_summary: str | None,
    ) -> Conversation:
        try:
            record = self.session.scalar(
                select(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .with_for_update()
            )
            if record is None:
                raise ConversationNotFoundError(f"会话不存在：{conversation_id}")
            record.topic_summary = topic_summary
            record.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(record)
            return conversation_from_record(record)
        except Exception:
            self.session.rollback()
            raise

    def update_topic_summary_if_empty(
        self,
        *,
        conversation_id: UUID,
        topic_summary: str,
    ) -> Conversation | None:
        try:
            record = self.session.scalar(
                select(ConversationRecord)
                .where(
                    ConversationRecord.id == conversation_id,
                    ConversationRecord.topic_summary.is_(None),
                )
                .with_for_update()
            )
            if record is None:
                return None
            record.topic_summary = topic_summary
            record.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(record)
            return conversation_from_record(record)
        except Exception:
            self.session.rollback()
            raise

    def update_pinned(
        self,
        *,
        conversation_id: UUID,
        is_pinned: bool,
    ) -> Conversation:
        try:
            record = self.session.scalar(
                select(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .with_for_update()
            )
            if record is None:
                raise ConversationNotFoundError(f"会话不存在：{conversation_id}")
            record.is_pinned = is_pinned
            record.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(record)
            return conversation_from_record(record)
        except Exception:
            self.session.rollback()
            raise

    def delete_conversation(self, *, conversation_id: UUID) -> None:
        """Delete the parent row and let database foreign keys cascade facts."""
        try:
            record = self.session.scalar(
                select(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .with_for_update()
            )
            if record is None:
                raise ConversationNotFoundError(f"会话不存在：{conversation_id}")
            self.session.delete(record)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        try:
            conversation_record = self.session.scalar(
                select(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .with_for_update()
            )
            if conversation_record is None:
                raise ConversationNotFoundError(f"会话不存在：{conversation_id}")

            current_sequence = self.session.scalar(
                select(func.coalesce(func.max(ConversationMessageRecord.sequence), 0)).where(
                    ConversationMessageRecord.conversation_id == conversation_id
                )
            )
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                sequence=int(current_sequence or 0) + 1,
            )
            message_record = message_to_record(message)
            conversation_record.updated_at = datetime.now(timezone.utc)
            self.session.add(message_record)
            self.session.commit()
            self.session.refresh(message_record)
            return message_from_record(message_record)
        except Exception:
            self.session.rollback()
            raise
