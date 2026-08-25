from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base


class ConversationRecord(Base):
    """Conversation 的 PostgreSQL 持久化记录。"""

    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint(
            "btrim(owner_subject) <> ''",
            name="chk_conversation_owner_subject_not_blank",
        ),
        CheckConstraint(
            "topic_summary IS NULL OR ("
            "btrim(topic_summary) <> '' AND topic_summary = btrim(topic_summary) "
            "AND position(E'\\n' in topic_summary) = 0 "
            "AND position(E'\\r' in topic_summary) = 0 "
            "AND char_length(topic_summary) <= 80)",
            name="chk_conversation_topic_summary_valid",
        ),
        Index("idx_conversation_owner_subject", "owner_subject"),
        Index(
            "idx_conversation_owner_pinned_updated",
            "owner_subject",
            "is_pinned",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    owner_subject: Mapped[str] = mapped_column(Text, nullable=False)
    topic_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    messages: Mapped[list["ConversationMessageRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ConversationMessageRecord(Base):
    """Conversation 中一条按顺序持久化的消息记录。"""

    __tablename__ = "conversation_message"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_conversation_message_conversation_sequence",
        ),
        CheckConstraint(
            "role IN ('system', 'user', 'assistant')",
            name="chk_conversation_message_role",
        ),
        CheckConstraint(
            "btrim(content) <> ''",
            name="chk_conversation_message_content_not_blank",
        ),
        CheckConstraint(
            "sequence > 0",
            name="chk_conversation_message_sequence_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(BIGINT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    conversation: Mapped["ConversationRecord"] = relationship(back_populates="messages")


class ConversationEventRecord(Base):
    """Conversation 的结构化 Agent 生命周期事件。"""

    __tablename__ = "conversation_event"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_conversation_event_conversation_sequence",
        ),
        CheckConstraint(
            "event_type IN ('agent_call', 'agent_result', 'agent_error')",
            name="chk_conversation_event_type",
        ),
        CheckConstraint(
            "btrim(call_id) <> ''",
            name="chk_conversation_event_call_id_not_blank",
        ),
        CheckConstraint(
            "btrim(capability_code) <> ''",
            name="chk_conversation_event_capability_not_blank",
        ),
        CheckConstraint(
            "sequence > 0",
            name="chk_conversation_event_sequence_positive",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="chk_conversation_event_payload_object",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    call_id: Mapped[str] = mapped_column(Text, nullable=False)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(BIGINT, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
