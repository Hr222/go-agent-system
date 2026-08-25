from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.conversation.application.access_service import (
    ConversationAccessService,
    ConversationResolveQuery,
)
from app.modules.conversation.domain import Conversation
from app.modules.conversation.ports.write_port import ConversationWritePort
from app.modules.security.domain.principal import RequestPrincipal


@dataclass(frozen=True, slots=True)
class ConversationPinCommand:
    principal: RequestPrincipal
    conversation_id: UUID
    is_pinned: bool


@dataclass(frozen=True, slots=True)
class ConversationDeleteCommand:
    principal: RequestPrincipal
    conversation_id: UUID


class ConversationManagementService:
    """在当前主体范围内执行会话整理操作。"""

    def __init__(self, *, access: ConversationAccessService, writer: ConversationWritePort) -> None:
        self._access = access
        self._writer = writer

    def pin(self, command: ConversationPinCommand) -> Conversation:
        if not isinstance(command, ConversationPinCommand):
            raise ValueError("会话置顶命令无效。")
        if not isinstance(command.conversation_id, UUID) or not isinstance(command.is_pinned, bool):
            raise ValueError("会话置顶命令无效。")
        conversation = self._resolve(command.principal, command.conversation_id)
        return self._writer.update_pinned(
            conversation_id=command.conversation_id,
            owner_subject=conversation.owner_subject,
            is_pinned=command.is_pinned,
        )

    def delete(self, command: ConversationDeleteCommand) -> None:
        if not isinstance(command, ConversationDeleteCommand):
            raise ValueError("会话删除命令无效。")
        if not isinstance(command.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        self._resolve(command.principal, command.conversation_id)
        self._writer.delete_conversation(conversation_id=command.conversation_id)

    def _resolve(self, principal: RequestPrincipal, conversation_id: UUID) -> Conversation:
        return self._access.resolve(
            ConversationResolveQuery(
                principal=principal,
                conversation_id=conversation_id,
            )
        )


__all__ = [
    "ConversationDeleteCommand",
    "ConversationManagementService",
    "ConversationPinCommand",
]
