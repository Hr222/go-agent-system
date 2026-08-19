from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.conversation_mapper import event_from_record, event_to_record
from app.infrastructure.persistence.models.conversation import (
    ConversationEventRecord,
    ConversationRecord,
)
from app.modules.conversation.domain import ConversationEvent
from app.modules.conversation.errors import ConversationNotFoundError
from app.modules.conversation.ports.event_port import (
    ConversationEventReadPort,
    ConversationEventWritePort,
)


class ConversationEventRepository(ConversationEventWritePort, ConversationEventReadPort):
    """Conversation 事件的 PostgreSQL 适配器。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def next_event_sequence(self, *, conversation_id: UUID) -> int:
        conversation = self.session.scalar(
            select(ConversationRecord)
            .where(ConversationRecord.id == conversation_id)
            .with_for_update()
        )
        if conversation is None:
            raise ConversationNotFoundError(f"会话不存在：{conversation_id}")
        current = self.session.scalar(
            select(func.coalesce(func.max(ConversationEventRecord.sequence), 0)).where(
                ConversationEventRecord.conversation_id == conversation_id
            )
        )
        return int(current or 0) + 1

    def save_event(self, event: ConversationEvent) -> ConversationEvent:
        try:
            # Locking the parent prevents two writers from allocating the same sequence.
            sequence = self.next_event_sequence(conversation_id=event.conversation_id)
            if sequence != event.sequence:
                raise ValueError("事件顺序不是当前会话的下一个顺序。")
            record = event_to_record(event)
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return event_from_record(record)
        except Exception:
            self.session.rollback()
            raise

    def list_events(
        self,
        *,
        conversation_id: UUID,
        call_id: str | None = None,
    ) -> tuple[ConversationEvent, ...]:
        try:
            statement = (
                select(ConversationEventRecord)
                .where(ConversationEventRecord.conversation_id == conversation_id)
                .order_by(ConversationEventRecord.sequence.asc())
            )
            if call_id is not None:
                statement = statement.where(ConversationEventRecord.call_id == call_id)
            records = self.session.scalars(statement).all()
            return tuple(event_from_record(record) for record in records)
        except Exception:
            self.session.rollback()
            raise


__all__ = ["ConversationEventRepository"]
