from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypeAlias
from uuid import UUID, uuid4

ConversationId: TypeAlias = UUID
MAX_TOPIC_SUMMARY_LENGTH = 80


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Conversation:
    """可长期引用的会话基础记录。"""

    owner_subject: str
    id: ConversationId = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    topic_summary: str | None = None
    is_pinned: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if not isinstance(self.is_pinned, bool):
            raise ValueError("会话置顶状态必须是布尔值。")
        if not isinstance(self.owner_subject, str) or not self.owner_subject.strip():
            raise ValueError("会话归属主体必须是非空文本。")
        object.__setattr__(self, "owner_subject", self.owner_subject.strip())
        if self.topic_summary is None:
            return
        if not isinstance(self.topic_summary, str):
            raise ValueError("话题概括必须是文本或 null。")
        if "\n" in self.topic_summary or "\r" in self.topic_summary:
            raise ValueError("话题概括必须是单行文本。")
        normalized = self.topic_summary.strip()
        if not normalized:
            object.__setattr__(self, "topic_summary", None)
            return
        if len(normalized) > MAX_TOPIC_SUMMARY_LENGTH:
            raise ValueError("话题概括不能超过 80 个字符。")
        object.__setattr__(self, "topic_summary", normalized)
