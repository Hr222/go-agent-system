from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class _ConversationLockState:
    lock: asyncio.Lock
    references: int = 0


class ConversationTurnLease:
    """一次普通 Conversation 轮次持有的进程内互斥租约。"""

    def __init__(
        self,
        *,
        coordinator: ConversationTurnCoordinator,
        conversation_id: UUID,
        state: _ConversationLockState,
    ) -> None:
        self._coordinator = coordinator
        self._conversation_id = conversation_id
        self._state = state
        self._released = False

    def release(self) -> None:
        """Release once so repeated stream cleanup cannot unlock another turn."""

        if self._released:
            return
        self._released = True
        self._coordinator._release(self._conversation_id, self._state)


class ConversationTurnCoordinator:
    """Serialize ordinary turns for one Conversation within one process."""

    def __init__(self) -> None:
        self._states: dict[UUID, _ConversationLockState] = {}

    @property
    def tracked_conversation_count(self) -> int:
        """Expose registry size for lifecycle verification and diagnostics."""

        return len(self._states)

    async def acquire(self, conversation_id: UUID) -> ConversationTurnLease:
        if not isinstance(conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")

        state = self._states.get(conversation_id)
        if state is None:
            state = _ConversationLockState(lock=asyncio.Lock())
            self._states[conversation_id] = state
        state.references += 1

        try:
            await state.lock.acquire()
        except BaseException:
            self._release_reference(conversation_id, state)
            raise

        return ConversationTurnLease(
            coordinator=self,
            conversation_id=conversation_id,
            state=state,
        )

    def _release(
        self,
        conversation_id: UUID,
        state: _ConversationLockState,
    ) -> None:
        state.lock.release()
        self._release_reference(conversation_id, state)

    def _release_reference(
        self,
        conversation_id: UUID,
        state: _ConversationLockState,
    ) -> None:
        state.references -= 1
        if state.references < 0:
            raise RuntimeError("会话锁引用计数无效。")
        if state.references == 0:
            current = self._states.get(conversation_id)
            if current is state:
                del self._states[conversation_id]


__all__ = ["ConversationTurnCoordinator", "ConversationTurnLease"]
