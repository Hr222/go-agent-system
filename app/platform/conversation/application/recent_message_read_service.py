from __future__ import annotations

from uuid import UUID

from app.platform.conversation.domain import Message
from app.platform.conversation.ports import (
    DEFAULT_RECENT_MESSAGE_WINDOW_SIZE,
    MAX_RECENT_MESSAGE_WINDOW_SIZE,
    ConversationRecentMessageReadPort,
    ConversationRecentMessageWindow,
)


class ConversationRecentMessageReadService:
    """读取用于上下文构建的有界最近消息快照。"""

    def __init__(self, read_port: ConversationRecentMessageReadPort) -> None:
        self.read_port = read_port

    def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int = DEFAULT_RECENT_MESSAGE_WINDOW_SIZE,
    ) -> ConversationRecentMessageWindow:
        """校验快照边界后读取不超过上限的最近消息。"""

        if not isinstance(conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if (
            isinstance(through_sequence, bool)
            or not isinstance(through_sequence, int)
            or through_sequence <= 0
        ):
            raise ValueError("上下文消息截止顺序号必须是正整数。")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("上下文消息数量上限必须是整数。")
        if not 1 <= limit <= MAX_RECENT_MESSAGE_WINDOW_SIZE:
            raise ValueError("上下文消息数量上限必须在 1 到 200 之间。")

        window = self.read_port.read_recent_messages(
            conversation_id=conversation_id,
            through_sequence=through_sequence,
            limit=limit,
        )
        self._validate_window(
            conversation_id=conversation_id,
            through_sequence=through_sequence,
            limit=limit,
            window=window,
        )
        return window

    @staticmethod
    def _validate_window(
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
        window: ConversationRecentMessageWindow,
    ) -> None:
        if not isinstance(window, ConversationRecentMessageWindow):
            raise ValueError("上下文最近消息快照无效。")
        if window.conversation_id != conversation_id:
            raise ValueError("上下文最近消息快照包含其他会话。")
        if len(window.messages) > limit:
            raise ValueError("上下文最近消息快照超过数量上限。")

        previous_sequence = 0
        for message in window.messages:
            if not isinstance(message, Message):
                raise ValueError("上下文最近消息快照包含无效消息。")
            if message.conversation_id != conversation_id:
                raise ValueError("上下文最近消息快照包含其他会话的消息。")
            if message.sequence <= previous_sequence:
                raise ValueError("上下文最近消息快照必须按顺序号严格递增。")
            if message.sequence > through_sequence:
                raise ValueError("上下文最近消息快照超出顺序截止边界。")
            previous_sequence = message.sequence


__all__ = ["ConversationRecentMessageReadService"]
