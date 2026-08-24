from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_conversation_access_service,
    get_conversation_history_read_service,
)
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.modules.conversation.application import ConversationAccessService
from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.conversation.errors import ConversationNotFoundError
from app.modules.conversation.ports import ConversationHistoryPage
from app.modules.security.domain.principal import RequestPrincipal

CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000101")


@dataclass
class FakeConversationAccessPort:
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
        if conversation is None or conversation.owner_subject != owner_subject:
            return None
        return conversation


class FakeConversationHistoryReadService:
    def __init__(
        self,
        conversation: Conversation,
        messages: tuple[Message, ...],
        *,
        raise_not_found: bool = False,
    ) -> None:
        self.conversation = conversation
        self.messages = messages
        self.raise_not_found = raise_not_found
        self.calls: list[dict[str, object]] = []

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int = 50,
        after_sequence: int | None = None,
    ) -> ConversationHistoryPage:
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "limit": limit,
                "after_sequence": after_sequence,
            }
        )
        if self.raise_not_found:
            raise ConversationNotFoundError("会话不存在")

        candidates = tuple(
            message
            for message in self.messages
            if after_sequence is None or message.sequence > after_sequence
        )
        page_messages = candidates[:limit]
        has_more = len(candidates) > limit
        return ConversationHistoryPage(
            conversation=self.conversation,
            messages=page_messages,
            has_more=has_more,
            next_after_sequence=page_messages[-1].sequence if has_more else None,
        )


def _message(sequence: int, role: MessageRole, content: str) -> Message:
    return Message(
        conversation_id=CONVERSATION_ID,
        role=role,
        content=content,
        sequence=sequence,
    )


def _client(
    access_port: FakeConversationAccessPort,
    history: FakeConversationHistoryReadService,
    principal: RequestPrincipal,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_conversation_access_service] = lambda: (
        ConversationAccessService(access_port)  # type: ignore[arg-type]
    )
    application.dependency_overrides[get_conversation_history_read_service] = lambda: history
    application.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(application)


def _conversation(*, owner_subject: str = "current-user") -> Conversation:
    return Conversation(id=CONVERSATION_ID, owner_subject=owner_subject)


def test_history_http_returns_ordered_browser_safe_first_page() -> None:
    conversation = _conversation()
    messages = tuple(
        [
            _message(1, MessageRole.USER, "第一条"),
            _message(2, MessageRole.ASSISTANT, "第二条"),
            _message(3, MessageRole.USER, "第三条"),
        ]
    )
    access_port = FakeConversationAccessPort({conversation.id: conversation})
    history = FakeConversationHistoryReadService(conversation, messages)

    response = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"conversation", "messages", "has_more", "next_after_sequence"}
    assert set(payload["conversation"]) == {
        "id",
        "created_at",
        "updated_at",
        "topic_summary",
        "is_pinned",
    }
    assert [message["sequence"] for message in payload["messages"]] == [1, 2]
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]
    assert payload["has_more"] is True
    assert payload["next_after_sequence"] == 2
    assert "events" not in payload
    assert "owner_subject" not in payload["conversation"]
    assert "permissions" not in payload
    assert history.calls == [
        {
            "conversation_id": conversation.id,
            "limit": 2,
            "after_sequence": None,
        }
    ]


def test_history_http_cursor_reads_only_messages_after_previous_page() -> None:
    conversation = _conversation()
    messages = tuple(
        _message(sequence, MessageRole.USER, f"消息 {sequence}")
        for sequence in range(1, 5)
    )
    access_port = FakeConversationAccessPort({conversation.id: conversation})
    history = FakeConversationHistoryReadService(conversation, messages)
    client = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    )

    first = client.get(f"/api/v1/conversations/{conversation.id}/messages?limit=2")
    second = client.get(
        f"/api/v1/conversations/{conversation.id}/messages?limit=2&after_sequence=2"
    )

    assert first.status_code == second.status_code == 200
    assert [message["sequence"] for message in first.json()["messages"]] == [1, 2]
    assert [message["sequence"] for message in second.json()["messages"]] == [3, 4]
    assert second.json()["has_more"] is False
    assert second.json()["next_after_sequence"] is None
    assert history.calls[-1]["after_sequence"] == 2


def test_history_http_returns_metadata_for_empty_conversation() -> None:
    conversation = _conversation()
    access_port = FakeConversationAccessPort({conversation.id: conversation})
    history = FakeConversationHistoryReadService(conversation, ())

    response = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages")

    assert response.status_code == 200
    assert response.json()["messages"] == []
    assert response.json()["has_more"] is False
    assert response.json()["next_after_sequence"] is None


def test_history_http_hides_other_owner_and_does_not_query_history() -> None:
    conversation = _conversation(owner_subject="other-user")
    access_port = FakeConversationAccessPort({conversation.id: conversation})
    history = FakeConversationHistoryReadService(
        conversation,
        (_message(1, MessageRole.USER, "秘密"),),
    )

    response = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "CONVERSATION_UNAVAILABLE",
            "message": "会话不可用。",
        }
    }
    assert history.calls == []
    assert "秘密" not in response.text


def test_history_http_hides_missing_conversation_and_history_failure() -> None:
    conversation = _conversation()
    access_port = FakeConversationAccessPort()
    history = FakeConversationHistoryReadService(
        conversation,
        (),
        raise_not_found=True,
    )

    missing = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages")

    assert missing.status_code == 404
    assert history.calls == []

    access_port.conversations[conversation.id] = conversation
    failure = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages")

    assert failure.status_code == 404
    assert failure.json()["detail"]["code"] == "CONVERSATION_UNAVAILABLE"


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=201", "after_sequence=0", "after_sequence=-1"],
)
def test_history_http_rejects_invalid_pagination_before_access_or_history(
    query: str,
) -> None:
    conversation = _conversation()
    access_port = FakeConversationAccessPort({conversation.id: conversation})
    history = FakeConversationHistoryReadService(conversation, ())

    response = _client(
        access_port,
        history,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get(f"/api/v1/conversations/{conversation.id}/messages?{query}")

    assert response.status_code == 422
    assert history.calls == []
