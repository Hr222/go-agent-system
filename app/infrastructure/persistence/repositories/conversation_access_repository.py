from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.conversation_mapper import (
    conversation_from_record,
    conversation_to_record,
)
from app.infrastructure.persistence.models.conversation import ConversationRecord
from app.modules.conversation.domain import Conversation
from app.modules.conversation.ports.access_port import ConversationAccessPort


class ConversationAccessRepository(ConversationAccessPort):
    """PostgreSQL owner-scoped adapter for Conversation access admission."""

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

    def get_owned_conversation(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
    ) -> Conversation | None:
        try:
            record = self.session.scalar(
                select(ConversationRecord).where(
                    ConversationRecord.id == conversation_id,
                    ConversationRecord.owner_subject == owner_subject,
                )
            )
            return conversation_from_record(record) if record is not None else None
        except Exception:
            self.session.rollback()
            raise


__all__ = ["ConversationAccessRepository"]
