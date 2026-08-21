from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_conversation_access_service
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.modules.conversation.application import ConversationAccessService
from app.modules.conversation.domain import Conversation
from app.modules.security.domain.principal import RequestPrincipal


@dataclass
class FakeConversationAccessPort:
    conversations: dict[UUID, Conversation] = field(default_factory=dict)
    messages: list[object] = field(default_factory=list)

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
        if conversation is None or conversation.owner_subject != owner_subject:
            return None
        return conversation


def _client(
    port: FakeConversationAccessPort,
    principal: RequestPrincipal,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_conversation_access_service] = lambda: (
        ConversationAccessService(port)  # type: ignore[arg-type]
    )
    application.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(application)


def test_create_owned_conversation_returns_only_empty_conversation_metadata() -> None:
    port = FakeConversationAccessPort()
    response = _client(
        port,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).post("/api/v1/conversations")

    assert response.status_code == 201
    payload = response.json()
    conversation_id = UUID(payload["id"])
    assert set(payload) == {"id", "created_at", "updated_at"}
    assert conversation_id in port.conversations
    assert port.conversations[conversation_id].owner_subject == "current-user"
    assert port.messages == []


def test_create_owned_conversation_rejects_missing_principal_without_persisting() -> None:
    port = FakeConversationAccessPort()
    response = _client(port, RequestPrincipal.anonymous()).post("/api/v1/conversations", json={})

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "code": "CONVERSATION_ACCESS_DENIED",
            "message": "会话不可用。",
        }
    }
    assert port.conversations == {}
    assert port.messages == []


@pytest.mark.parametrize(
    "payload",
    [
        {"owner_subject": "other-user"},
        {"content": "不应追加为消息"},
        {"permissions": ["agent:tender:execute"]},
        {"model": "provider-model"},
    ],
)
def test_create_owned_conversation_rejects_caller_controlled_fields(
    payload: dict[str, object],
) -> None:
    port = FakeConversationAccessPort()
    response = _client(
        port,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).post("/api/v1/conversations", json=payload)

    assert response.status_code == 422
    assert port.conversations == {}
    assert port.messages == []
