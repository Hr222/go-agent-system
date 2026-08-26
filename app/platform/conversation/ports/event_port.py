from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.platform.conversation.domain import ConversationEvent


class ConversationEventWritePort(Protocol):
    def next_event_sequence(self, *, conversation_id: UUID) -> int: ...

    def save_event(self, event: ConversationEvent) -> ConversationEvent: ...


class ConversationEventReadPort(Protocol):
    def list_events(
        self,
        *,
        conversation_id: UUID,
        call_id: str | None = None,
    ) -> tuple[ConversationEvent, ...]: ...


__all__ = ["ConversationEventReadPort", "ConversationEventWritePort"]
