from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TypeAlias
from uuid import UUID, uuid4

MessageId: TypeAlias = UUID


class MessageRole(str, Enum):
    """当前可持久化的最小对话消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Message:
    """归属于一个会话、按顺序保存的消息。"""

    conversation_id: UUID
    role: MessageRole
    content: str
    sequence: int
    id: MessageId = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("消息标识必须是 UUID。")
        if not isinstance(self.conversation_id, UUID):
            raise ValueError("消息所属会话标识必须是 UUID。")
        if not isinstance(self.role, MessageRole):
            raise ValueError("消息角色无效。")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("消息内容不能为空。")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence <= 0
        ):
            raise ValueError("消息顺序号必须是正整数。")
