from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationResolveQuery,
)
from app.platform.conversation.domain import Conversation
from app.platform.conversation.errors import ConversationAccessDeniedError
from app.platform.security.domain.principal import RequestPrincipal


@dataclass
class FakeConversationAccessPort:
    conversations: dict[UUID, Conversation] = field(default_factory=dict)
    saved: list[Conversation] = field(default_factory=list)
    queries: list[tuple[UUID, str]] = field(default_factory=list)

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.saved.append(conversation)
        self.conversations[conversation.id] = conversation
        return conversation

    def get_owned_conversation(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
    ) -> Conversation | None:
        self.queries.append((conversation_id, owner_subject))
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation.owner_subject != owner_subject:
            return None
        return conversation


def _principal(subject: str | None = "user-1") -> RequestPrincipal:
    return RequestPrincipal(subject=subject, authenticated=subject is not None)


def test_create_binds_a_new_empty_conversation_to_the_trusted_subject() -> None:
    port = FakeConversationAccessPort()
    service = ConversationAccessService(port)

    conversation = service.create(ConversationCreateCommand(principal=_principal()))

    assert conversation.owner_subject == "user-1"
    assert port.saved == [conversation]


def test_resolve_returns_only_the_callers_owned_conversation() -> None:
    conversation = Conversation(id=uuid4(), owner_subject="user-1")
    port = FakeConversationAccessPort({conversation.id: conversation})
    service = ConversationAccessService(port)

    resolved = service.resolve(
        ConversationResolveQuery(principal=_principal(), conversation_id=conversation.id)
    )

    assert resolved == conversation
    assert port.queries == [(conversation.id, "user-1")]


@pytest.mark.parametrize(
    "principal, conversation_id",
    [
        (_principal("user-2"), uuid4()),
        (_principal(), uuid4()),
        (_principal(None), uuid4()),
    ],
)
def test_resolve_hides_missing_owner_and_unknown_conversations(
    principal: RequestPrincipal,
    conversation_id: UUID,
) -> None:
    owned = Conversation(id=uuid4(), owner_subject="user-1")
    port = FakeConversationAccessPort({owned.id: owned})
    service = ConversationAccessService(port)

    with pytest.raises(ConversationAccessDeniedError, match="会话不可用"):
        service.resolve(
            ConversationResolveQuery(principal=principal, conversation_id=conversation_id)
        )

    if principal.subject is None:
        assert port.queries == []
    else:
        assert port.queries == [(conversation_id, principal.subject)]


def test_create_rejects_a_missing_subject_without_writing() -> None:
    port = FakeConversationAccessPort()

    with pytest.raises(ConversationAccessDeniedError, match="会话不可用"):
        ConversationAccessService(port).create(
            ConversationCreateCommand(principal=RequestPrincipal.anonymous())
        )

    assert port.saved == []
