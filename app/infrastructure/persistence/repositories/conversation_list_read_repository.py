from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models.conversation import ConversationRecord
from app.modules.conversation.ports.read_port import (
    ConversationListCursor,
    ConversationListReadPort,
    ConversationSummary,
    ConversationSummaryPage,
)


class ConversationListReadRepository(ConversationListReadPort):
    """按主体和稳定游标读取 Conversation 摘要的 PostgreSQL adapter。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_owned(
        self,
        *,
        owner_subject: str,
        limit: int,
        cursor: ConversationListCursor | None,
    ) -> ConversationSummaryPage:
        try:
            statement = select(ConversationRecord).where(
                ConversationRecord.owner_subject == owner_subject
            )
            if cursor is not None:
                conditions = [
                    and_(
                        ConversationRecord.is_pinned.is_(cursor.is_pinned),
                        ConversationRecord.updated_at < cursor.updated_at,
                    ),
                    and_(
                        ConversationRecord.is_pinned.is_(cursor.is_pinned),
                        ConversationRecord.updated_at == cursor.updated_at,
                        ConversationRecord.id < cursor.id,
                    ),
                ]
                if cursor.is_pinned:
                    conditions.insert(0, ConversationRecord.is_pinned.is_(False))
                statement = statement.where(or_(*conditions))

            statement = (
                statement.order_by(
                    ConversationRecord.is_pinned.desc(),
                    ConversationRecord.updated_at.desc(),
                    ConversationRecord.id.desc(),
                )
                .limit(limit + 1)
            )
            records = list(self.session.scalars(statement).all())
            has_more = len(records) > limit
            page_records = records[:limit]
            summaries = tuple(
                ConversationSummary(
                    id=record.id,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    topic_summary=record.topic_summary,
                    is_pinned=record.is_pinned,
                )
                for record in page_records
            )
            return ConversationSummaryPage(
                conversations=summaries,
                has_more=has_more,
                next_cursor=(
                    ConversationListCursor(
                        updated_at=summaries[-1].updated_at,
                        id=summaries[-1].id,
                        is_pinned=summaries[-1].is_pinned,
                    )
                    if has_more
                    else None
                ),
            )
        except Exception:
            self.session.rollback()
            raise


__all__ = ["ConversationListReadRepository"]
