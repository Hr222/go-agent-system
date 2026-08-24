from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.conversation.domain import Conversation, Message

DEFAULT_HISTORY_PAGE_SIZE = 50
MAX_HISTORY_PAGE_SIZE = 200
DEFAULT_CONVERSATION_LIST_PAGE_SIZE = 50
MAX_CONVERSATION_LIST_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """用于发现和恢复会话的最小只读摘要。"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    topic_summary: str | None = None
    is_pinned: bool = False


@dataclass(frozen=True, slots=True)
class ConversationListCursor:
    """按 updated_at、id 倒序列表的稳定游标。"""

    updated_at: datetime
    id: UUID
    is_pinned: bool = False


@dataclass(frozen=True, slots=True)
class ConversationSummaryPage:
    """一次主体范围会话摘要列表结果页。"""

    conversations: tuple[ConversationSummary, ...]
    has_more: bool
    next_cursor: ConversationListCursor | None


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


class ConversationListReadPort(Protocol):
    """Conversation 主体范围摘要列表依赖的持久化端口。"""

    def list_owned(
        self,
        *,
        owner_subject: str,
        limit: int,
        cursor: ConversationListCursor | None,
    ) -> ConversationSummaryPage: ...
