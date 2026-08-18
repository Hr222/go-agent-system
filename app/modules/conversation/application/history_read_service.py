from __future__ import annotations

from uuid import UUID

from app.modules.conversation.ports.read_port import (
    DEFAULT_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
    ConversationHistoryPage,
    ConversationReadPort,
)


class ConversationHistoryReadService:
    """读取会话元数据和有序消息历史的应用服务。"""

    def __init__(self, read_port: ConversationReadPort) -> None:
        self.read_port = read_port

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
        after_sequence: int | None = None,
    ) -> ConversationHistoryPage:
        """校验游标分页参数后读取一页历史。"""

        if not isinstance(conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("历史页大小必须是整数。")
        if not 1 <= limit <= MAX_HISTORY_PAGE_SIZE:
            raise ValueError("历史页大小必须在 1 到 200 之间。")
        if after_sequence is not None and (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence <= 0
        ):
            raise ValueError("历史游标必须是正整数。")

        return self.read_port.read_history(
            conversation_id=conversation_id,
            limit=limit,
            after_sequence=after_sequence,
        )
