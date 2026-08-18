from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.conversation.domain import Conversation, Message, MessageRole


class ConversationWritePort(Protocol):
    """Conversation 写入用例依赖的持久化端口。"""

    def save_conversation(self, conversation: Conversation) -> Conversation: ...

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message: ...
