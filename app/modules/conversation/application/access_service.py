from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.conversation.domain import Conversation
from app.modules.conversation.errors import ConversationAccessDeniedError
from app.modules.conversation.ports.access_port import ConversationAccessPort
from app.modules.security.domain.principal import RequestPrincipal


@dataclass(frozen=True, slots=True)
class ConversationCreateCommand:
    principal: RequestPrincipal


@dataclass(frozen=True, slots=True)
class ConversationResolveQuery:
    principal: RequestPrincipal
    conversation_id: UUID


class ConversationAccessService:
    """Create or resolve a conversation only within a trusted owner's scope."""

    def __init__(self, access_port: ConversationAccessPort) -> None:
        self._access_port = access_port

    def create(self, command: ConversationCreateCommand) -> Conversation:
        owner_subject = self._owner_subject(command.principal)
        return self._access_port.save_conversation(
            Conversation(owner_subject=owner_subject)
        )

    def resolve(self, query: ConversationResolveQuery) -> Conversation:
        owner_subject = self._owner_subject(query.principal)
        if not isinstance(query.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        conversation = self._access_port.get_owned_conversation(
            conversation_id=query.conversation_id,
            owner_subject=owner_subject,
        )
        if conversation is None:
            raise ConversationAccessDeniedError("会话不可用。")
        return conversation

    @staticmethod
    def _owner_subject(principal: RequestPrincipal) -> str:
        if not isinstance(principal, RequestPrincipal):
            raise ConversationAccessDeniedError("会话不可用。")
        if not isinstance(principal.subject, str) or not principal.subject.strip():
            raise ConversationAccessDeniedError("会话不可用。")
        return principal.subject.strip()


__all__ = [
    "ConversationAccessService",
    "ConversationCreateCommand",
    "ConversationResolveQuery",
]
