from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.conversation.domain import Conversation, Message

DEFAULT_HISTORY_PAGE_SIZE = 50
MAX_HISTORY_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class ConversationHistoryPage:
    """一次历史读取的领域结果页。"""

    conversation: Conversation
    messages: tuple[Message, ...]
    has_more: bool
    next_after_sequence: int | None


class ConversationReadPort(Protocol):
    """Conversation 历史读取用例依赖的持久化端口。"""

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage: ...
