from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.conversation.domain import Conversation, Message, MessageRole

DEFAULT_PINNED_CONVERSATION_LIMIT = 10


class ConversationWritePort(Protocol):
    """Conversation 写入用例依赖的持久化端口。"""

    def save_conversation(self, conversation: Conversation) -> Conversation: ...

    def update_topic_summary(
        self,
        *,
        conversation_id: UUID,
        topic_summary: str | None,
    ) -> Conversation: ...

    def update_topic_summary_if_empty(
        self,
        *,
        conversation_id: UUID,
        topic_summary: str,
    ) -> Conversation | None: ...

    def update_pinned(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
        is_pinned: bool,
    ) -> Conversation: ...

    def delete_conversation(self, *, conversation_id: UUID) -> None: ...

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message: ...
