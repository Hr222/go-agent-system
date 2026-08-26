from __future__ import annotations

from app.platform.conversation.ports.read_port import (
    DEFAULT_CONVERSATION_LIST_PAGE_SIZE,
    MAX_CONVERSATION_LIST_PAGE_SIZE,
    ConversationListCursor,
    ConversationListReadPort,
    ConversationSummaryPage,
)


class ConversationListReadService:
    """读取当前主体可见的 Conversation 最小摘要列表。"""

    def __init__(self, read_port: ConversationListReadPort) -> None:
        self.read_port = read_port

    def list_owned(
        self,
        *,
        owner_subject: str,
        limit: int = DEFAULT_CONVERSATION_LIST_PAGE_SIZE,
        cursor: ConversationListCursor | None = None,
    ) -> ConversationSummaryPage:
        if not isinstance(owner_subject, str) or not owner_subject.strip():
            raise ValueError("会话列表主体不能为空。")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("会话列表页大小必须是整数。")
        if not 1 <= limit <= MAX_CONVERSATION_LIST_PAGE_SIZE:
            raise ValueError("会话列表页大小必须在 1 到 200 之间。")
        if cursor is not None and not isinstance(cursor, ConversationListCursor):
            raise ValueError("会话列表游标无效。")

        return self.read_port.list_owned(
            owner_subject=owner_subject.strip(),
            limit=limit,
            cursor=cursor,
        )


__all__ = ["ConversationListReadService"]
