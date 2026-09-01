from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.ports import ConversationRecentMessageWindow
from app.platform.dialogue.ports import (
    StreamingConversationPersistencePort,
    StreamingConversationPersistenceWorkerFactoryPort,
    StreamingConversationPersistenceWorkerPort,
)
from app.platform.security.domain.principal import RequestPrincipal
from app.shared.async_task import await_shielded_task


class ThreadedStreamingConversationPersistence(StreamingConversationPersistencePort):
    """把同步 Conversation 能力隔离到每次操作独立的线程 worker。"""

    def __init__(
        self,
        worker_factory: StreamingConversationPersistenceWorkerFactoryPort,
    ) -> None:
        self._worker_factory = worker_factory

    async def create_conversation(self, *, principal: RequestPrincipal) -> Conversation:
        return await self._run(
            lambda worker: worker.create_conversation(principal=principal)
        )

    async def resolve_conversation(
        self,
        *,
        principal: RequestPrincipal,
        conversation_id: UUID,
    ) -> Conversation:
        return await self._run(
            lambda worker: worker.resolve_conversation(
                principal=principal,
                conversation_id=conversation_id,
            )
        )

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        return await self._run(
            lambda worker: worker.append_message(
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
        )

    async def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow:
        return await self._run(
            lambda worker: worker.read_recent_messages(
                conversation_id=conversation_id,
                through_sequence=through_sequence,
                limit=limit,
            )
        )

    async def _run(self, operation: Callable[[StreamingConversationPersistenceWorkerPort], object]):
        """操作取消时先等待线程收口，避免租约早于数据库事实释放。"""

        task = asyncio.create_task(asyncio.to_thread(self._run_sync, operation))
        return await await_shielded_task(task)

    def _run_sync(
        self,
        operation: Callable[[StreamingConversationPersistenceWorkerPort], object],
    ) -> object:
        worker: StreamingConversationPersistenceWorkerPort | None = None
        try:
            worker = self._worker_factory.create()
            return operation(worker)
        finally:
            if worker is not None:
                worker.close()


__all__ = ["ThreadedStreamingConversationPersistence"]
