from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypeAlias
from uuid import UUID, uuid4

ConversationId: TypeAlias = UUID


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Conversation:
    """可长期引用的会话基础记录。"""

    owner_subject: str
    id: ConversationId = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if not isinstance(self.owner_subject, str) or not self.owner_subject.strip():
            raise ValueError("会话归属主体必须是非空文本。")
        object.__setattr__(self, "owner_subject", self.owner_subject.strip())
