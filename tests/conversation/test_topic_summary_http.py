from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_conversation_topic_summary_update_service,
)
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.modules.conversation.application import (
    ConversationAccessService,
    ConversationTopicSummaryUpdateService,
    ConversationWriteService,
)
from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.security.domain.principal import RequestPrincipal


@dataclass
class FakePort:
    conversations: dict[UUID, Conversation] = field(default_factory=dict)

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations[conversation.id] = conversation
        return conversation

    def append_message(self, *, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        return Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=1,
        )

    def update_topic_summary(
        self, *, conversation_id: UUID, topic_summary: str | None
    ) -> Conversation:
        current = self.conversations[conversation_id]
        updated = Conversation(
            id=current.id,
            owner_subject=current.owner_subject,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
            topic_summary=topic_summary,
        )
        self.conversations[conversation_id] = updated
        return updated

    def update_topic_summary_if_empty(
        self, *, conversation_id: UUID, topic_summary: str
    ) -> Conversation | None:
        current = self.conversations[conversation_id]
        if current.topic_summary is not None:
            return None
        return self.update_topic_summary(
            conversation_id=conversation_id, topic_summary=topic_summary
        )

    def get_owned_conversation(
        self, *, conversation_id: UUID, owner_subject: str
    ) -> Conversation | None:
        current = self.conversations.get(conversation_id)
        return current if current is not None and current.owner_subject == owner_subject else None


def _client(port: FakePort, principal: RequestPrincipal) -> TestClient:
    app = create_app()
    access = ConversationAccessService(port)  # type: ignore[arg-type]
    writer = ConversationWriteService(port)  # type: ignore[arg-type]
    service = ConversationTopicSummaryUpdateService(access=access, writer=writer)
    app.dependency_overrides[get_conversation_topic_summary_update_service] = lambda: service
    app.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(app)


def test_topic_summary_http_updates_and_clears_owned_conversation() -> None:
    port = FakePort()
    conversation = port.save_conversation(Conversation(owner_subject="current-user"))
    client = _client(port, RequestPrincipal(subject="current-user", authenticated=True))

    response = client.patch(
        f"/api/v1/conversations/{conversation.id}/topic-summary",
        json={"topic_summary": "人工修正标题"},
    )
    assert response.status_code == 200
    assert response.json()["topic_summary"] == "人工修正标题"

    cleared = client.patch(
        f"/api/v1/conversations/{conversation.id}/topic-summary",
        json={"topic_summary": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["topic_summary"] is None


def test_topic_summary_http_hides_other_owner_and_rejects_invalid_payload() -> None:
    port = FakePort()
    conversation = port.save_conversation(Conversation(owner_subject="other-user"))
    client = _client(port, RequestPrincipal(subject="current-user", authenticated=True))

    forbidden_target = client.patch(
        f"/api/v1/conversations/{conversation.id}/topic-summary",
        json={"topic_summary": "越权标题"},
    )
    assert forbidden_target.status_code == 404
    assert port.conversations[conversation.id].topic_summary is None

    invalid = client.patch(
        f"/api/v1/conversations/{conversation.id}/topic-summary",
        json={"topic_summary": "标题", "extra": True},
    )
    assert invalid.status_code == 422
