from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic

from app.modules.dialogue.application.agent_invocation import DialogueAgentInvocationCommand


@dataclass(frozen=True, slots=True)
class PendingAgentInvocation:
    command: DialogueAgentInvocationCommand
    subject: str | None
    expires_at: float


class InMemoryPendingAgentInvocationStore:
    """短期、主体绑定的一次性确认状态；真实事实仍由 Conversation 事件保存。"""

    def __init__(self, *, ttl_seconds: float = 300.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, PendingAgentInvocation] = {}
        self._lock = Lock()

    def save(
        self,
        *,
        proposal_id: str,
        command: DialogueAgentInvocationCommand,
    ) -> None:
        with self._lock:
            self._purge()
            self._entries[proposal_id] = PendingAgentInvocation(
                command=command,
                subject=command.principal.subject,
                expires_at=monotonic() + self._ttl_seconds,
            )

    def read(self, *, proposal_id: str, subject: str | None) -> PendingAgentInvocation | None:
        with self._lock:
            self._purge()
            entry = self._entries.get(proposal_id)
            if entry is None or entry.subject != subject:
                return None
            return entry

    def consume(
        self,
        *,
        proposal_id: str,
        subject: str | None,
    ) -> PendingAgentInvocation | None:
        with self._lock:
            self._purge()
            entry = self._entries.get(proposal_id)
            if entry is None or entry.subject != subject:
                return None
            del self._entries[proposal_id]
            return entry

    def _purge(self) -> None:
        now = monotonic()
        for proposal_id, entry in tuple(self._entries.items()):
            if entry.expires_at <= now:
                del self._entries[proposal_id]


__all__ = ["InMemoryPendingAgentInvocationStore", "PendingAgentInvocation"]
