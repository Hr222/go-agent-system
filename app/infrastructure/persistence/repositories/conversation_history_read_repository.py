from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.conversation_mapper import (
    conversation_from_record,
    message_from_record,
)
from app.infrastructure.persistence.models.conversation import (
    ConversationMessageRecord,
    ConversationRecord,
)
from app.modules.conversation.errors import ConversationNotFoundError
from app.modules.conversation.ports.read_port import (
    ConversationHistoryPage,
    ConversationReadPort,
)


class ConversationHistoryReadRepository(ConversationReadPort):
    """Conversation 历史 PostgreSQL 只读适配器。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage:
        try:
            conversation_record = self.session.scalar(
                select(ConversationRecord).where(ConversationRecord.id == conversation_id)
            )
            if conversation_record is None:
                raise ConversationNotFoundError(f"会话不存在：{conversation_id}")

            statement = (
                select(ConversationMessageRecord)
                .where(ConversationMessageRecord.conversation_id == conversation_id)
                .order_by(ConversationMessageRecord.sequence.asc())
                .limit(limit + 1)
            )
            if after_sequence is not None:
                statement = statement.where(
                    ConversationMessageRecord.sequence > after_sequence
                )

            records = list(self.session.scalars(statement).all())
            has_more = len(records) > limit
            page_records = records[:limit]
            messages = tuple(message_from_record(record) for record in page_records)
            return ConversationHistoryPage(
                conversation=conversation_from_record(conversation_record),
                messages=messages,
                has_more=has_more,
                next_after_sequence=messages[-1].sequence if has_more else None,
            )
        except Exception:
            self.session.rollback()
            raise
