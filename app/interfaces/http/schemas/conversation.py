from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConversationCreateRequest(BaseModel):
    """Creating a conversation accepts no caller-controlled attributes."""

    model_config = ConfigDict(extra="forbid")


class ConversationResponse(BaseModel):
    """The minimum browser-safe representation of a Conversation."""

    id: UUID
    created_at: datetime
    updated_at: datetime


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
