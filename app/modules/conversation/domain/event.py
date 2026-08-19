from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

ConversationEventType = Literal["agent_call", "agent_result", "agent_error"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ConversationEvent:
    """Conversation 中不应伪装成自然语言消息的结构化事件。"""

    conversation_id: UUID
    event_type: ConversationEventType
    call_id: str
    capability_code: str
    sequence: int
    payload: dict[str, object]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.conversation_id, UUID):
            raise ValueError("事件标识和会话标识必须是 UUID。")
        if self.event_type not in {"agent_call", "agent_result", "agent_error"}:
            raise ValueError("事件类型无效。")
        for value, label in (
            (self.call_id, "调用标识"),
            (self.capability_code, "能力代码"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label}不能为空。")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence <= 0
        ):
            raise ValueError("事件顺序必须是正整数。")
        if not isinstance(self.payload, dict) or not self.payload:
            raise ValueError("事件载荷必须是非空 JSON 对象。")
        try:
            normalized = json.loads(
                json.dumps(self.payload, ensure_ascii=False, allow_nan=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("事件载荷必须可安全序列化为 JSON。") from exc
        if not isinstance(normalized, dict):
            raise ValueError("事件载荷必须是 JSON 对象。")
        object.__setattr__(self, "payload", normalized)


__all__ = ["ConversationEvent", "ConversationEventType"]
