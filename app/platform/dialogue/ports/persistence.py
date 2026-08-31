from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.ports import ConversationRecentMessageWindow
from app.platform.security.domain.principal import RequestPrincipal


class StreamingConversationPersistenceWorkerPort(Protocol):
    """一次短数据库操作使用的同步 worker。"""

    def create_conversation(self, *, principal: RequestPrincipal) -> Conversation: ...

    def resolve_conversation(
        self,
        *,
        principal: RequestPrincipal,
        conversation_id: UUID,
    ) -> Conversation: ...

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message: ...

    def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow: ...

    def close(self) -> None: ...


class StreamingConversationPersistenceWorkerFactoryPort(Protocol):
    """创建每次操作独立使用的同步 worker。"""

    def create(self) -> StreamingConversationPersistenceWorkerPort: ...


class StreamingConversationPersistencePort(Protocol):
    """普通流式 Dialogue 使用的异步 Conversation 持久化能力。"""

    async def create_conversation(
        self,
        *,
        principal: RequestPrincipal,
    ) -> Conversation: ...

    async def resolve_conversation(
        self,
        *,
        principal: RequestPrincipal,
        conversation_id: UUID,
    ) -> Conversation: ...

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message: ...

    async def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow: ...

__all__ = [
    "StreamingConversationPersistencePort",
    "StreamingConversationPersistenceWorkerFactoryPort",
    "StreamingConversationPersistenceWorkerPort",
]
