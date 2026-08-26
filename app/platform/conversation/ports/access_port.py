from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.platform.conversation.domain import Conversation


class ConversationAccessPort(Protocol):
    """Owner-scoped persistence operations needed before using a conversation."""

    def save_conversation(self, conversation: Conversation) -> Conversation: ...

    def get_owned_conversation(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
    ) -> Conversation | None: ...


__all__ = ["ConversationAccessPort"]
