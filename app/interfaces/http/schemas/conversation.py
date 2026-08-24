from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ConversationCreateRequest(BaseModel):
    """Creating a conversation accepts no caller-controlled attributes."""

    model_config = ConfigDict(extra="forbid")


class ConversationTopicSummaryUpdateRequest(BaseModel):
    """设置或显式清除会话话题概括。"""

    model_config = ConfigDict(extra="forbid")

    topic_summary: str | None

    @field_validator("topic_summary")
    @classmethod
    def validate_topic_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("话题概括不能为空；清除请使用 null。")
        if "\n" in normalized or "\r" in normalized:
            raise ValueError("话题概括必须是单行文本。")
        if len(normalized) > 80:
            raise ValueError("话题概括不能超过 80 个字符。")
        return normalized


class ConversationPinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_pinned: bool


class ConversationResponse(BaseModel):
    """The minimum browser-safe representation of a Conversation."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    topic_summary: str | None = None
    is_pinned: bool = False


class ConversationMessageResponse(BaseModel):
    id: UUID
    role: Literal["system", "user", "assistant"]
    content: str
    sequence: int
    created_at: datetime


class ConversationMessagePageResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[ConversationMessageResponse]
    has_more: bool
    next_after_sequence: int | None


class ConversationSummaryResponse(BaseModel):
    """The minimum browser-safe representation used in conversation lists."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    topic_summary: str | None = None
    is_pinned: bool = False


class ConversationSummaryPageResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]
    has_more: bool
    next_cursor: str | None
