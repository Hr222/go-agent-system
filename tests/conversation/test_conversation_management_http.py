from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_conversation_access_service,
    get_conversation_management_service,
)
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.modules.conversation.application import (
    ConversationAccessService,
    ConversationManagementService,
)
from app.modules.conversation.domain import Conversation
from app.modules.conversation.errors import (
    ConversationNotFoundError,
    ConversationPinLimitExceededError,
)
from app.modules.security.domain.principal import RequestPrincipal

CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000000301")


@dataclass
class FakeAccessPort:
    conversations: dict[UUID, Conversation] = field(default_factory=dict)

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations[conversation.id] = conversation
        return conversation

    def get_owned_conversation(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
    ) -> Conversation | None:
        conversation = self.conversations.get(conversation_id)
        return (
            conversation
            if conversation and conversation.owner_subject == owner_subject
            else None
        )


@dataclass
class FakeWriter:
    conversations: dict[UUID, Conversation]
    deleted: list[UUID] = field(default_factory=list)
    pin_limit_reached: bool = False

    def update_pinned(
        self,
        *,
        conversation_id: UUID,
        owner_subject: str,
        is_pinned: bool,
    ) -> Conversation:
        current = self.conversations.get(conversation_id)
        if current is None or current.owner_subject != owner_subject:
            raise ConversationNotFoundError("missing")
        if self.pin_limit_reached:
            raise ConversationPinLimitExceededError("limit")
        updated = Conversation(
            id=current.id,
            owner_subject=current.owner_subject,
            created_at=current.created_at,
            updated_at=current.updated_at,
            topic_summary=current.topic_summary,
            is_pinned=is_pinned,
        )
        self.conversations[conversation_id] = updated
        return updated

    def delete_conversation(self, *, conversation_id: UUID) -> None:
        if conversation_id not in self.conversations:
            raise ConversationNotFoundError("missing")
        self.deleted.append(conversation_id)
        del self.conversations[conversation_id]


def _client(
    access_port: FakeAccessPort,
    writer: FakeWriter,
    principal: RequestPrincipal,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_conversation_access_service] = lambda: (
        ConversationAccessService(access_port)
    )
    application.dependency_overrides[get_conversation_management_service] = lambda: (
        ConversationManagementService(
            access=ConversationAccessService(access_port),
            writer=writer,  # type: ignore[arg-type]
        )
    )
    application.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(application)


def test_pin_and_delete_are_owner_scoped() -> None:
    own = Conversation(id=CONVERSATION_ID, owner_subject="current-user")
    other = Conversation(owner_subject="other")
    access = FakeAccessPort({own.id: own, other.id: other})
    writer = FakeWriter(access.conversations)
    client = _client(
        access,
        writer,
        RequestPrincipal(subject="current-user", authenticated=True),
    )

    pinned = client.patch(
        f"/api/v1/conversations/{CONVERSATION_ID}/pin",
        json={"is_pinned": True},
    )
    assert pinned.status_code == 200
    assert pinned.json()["is_pinned"] is True

    deleted = client.delete(f"/api/v1/conversations/{CONVERSATION_ID}")
    assert deleted.status_code == 204
    assert writer.deleted == [CONVERSATION_ID]

    forbidden = client.patch(
        f"/api/v1/conversations/{other.id}/pin",
        json={"is_pinned": True},
    )
    assert forbidden.status_code == 404
    assert other.id in access.conversations


def test_management_rejects_anonymous_and_invalid_payload() -> None:
    own = Conversation(id=CONVERSATION_ID, owner_subject="current-user")
    access = FakeAccessPort({own.id: own})
    writer = FakeWriter(access.conversations)
    anonymous = _client(access, writer, RequestPrincipal.anonymous())

    response = anonymous.patch(
        f"/api/v1/conversations/{CONVERSATION_ID}/pin",
        json={"is_pinned": True},
    )
    assert response.status_code == 404
    assert own.is_pinned is False

    invalid = _client(
        access,
        writer,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).patch(
        f"/api/v1/conversations/{CONVERSATION_ID}/pin",
        json={"is_pinned": True, "extra": "forbidden"},
    )
    assert invalid.status_code == 422


def test_pin_limit_conflict_is_controlled_and_preserves_the_conversation() -> None:
    own = Conversation(id=CONVERSATION_ID, owner_subject="current-user")
    access = FakeAccessPort({own.id: own})
    client = _client(
        access,
        FakeWriter(access.conversations, pin_limit_reached=True),
        RequestPrincipal(subject="current-user", authenticated=True),
    )

    response = client.patch(
        f"/api/v1/conversations/{CONVERSATION_ID}/pin",
        json={"is_pinned": True},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "CONVERSATION_PIN_LIMIT_REACHED",
        "message": "最多置顶 10 个会话，请先取消一个。",
    }
    assert access.conversations[CONVERSATION_ID].is_pinned is False


def test_delete_rejects_anonymous_other_invalid_and_missing_targets() -> None:
    own = Conversation(id=CONVERSATION_ID, owner_subject="current-user")
    other = Conversation(owner_subject="other-user")
    access = FakeAccessPort({own.id: own, other.id: other})
    writer = FakeWriter(access.conversations)

    anonymous = _client(access, writer, RequestPrincipal.anonymous())
    anonymous_response = anonymous.delete(f"/api/v1/conversations/{own.id}")
    assert anonymous_response.status_code == 404
    assert own.id in access.conversations
    assert writer.deleted == []

    current = _client(
        access,
        writer,
        RequestPrincipal(subject="current-user", authenticated=True),
    )
    forbidden = current.delete(f"/api/v1/conversations/{other.id}")
    assert forbidden.status_code == 404
    assert other.id in access.conversations
    assert writer.deleted == []

    invalid = current.delete("/api/v1/conversations/not-a-uuid")
    assert invalid.status_code == 422
    missing = current.delete(f"/api/v1/conversations/{uuid4()}")
    assert missing.status_code == 404
    assert own.id in access.conversations
    assert writer.deleted == []
