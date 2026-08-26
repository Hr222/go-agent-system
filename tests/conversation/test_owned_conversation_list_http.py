from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.interfaces.http.conversation_cursor import decode_conversation_cursor
from app.interfaces.http.dependencies import (
    get_conversation_access_service,
    get_conversation_list_read_service,
)
from app.interfaces.http.security import get_request_principal
from app.main import create_app
from app.platform.conversation.application import ConversationAccessService
from app.platform.conversation.domain import Conversation
from app.platform.conversation.ports import (
    ConversationListCursor,
    ConversationSummary,
    ConversationSummaryPage,
)
from app.platform.security.domain.principal import RequestPrincipal

CONVERSATION_ONE = UUID("00000000-0000-0000-0000-000000000221")
CONVERSATION_TWO = UUID("00000000-0000-0000-0000-000000000222")


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


class FakeConversationListReadService:
    def __init__(self, page: ConversationSummaryPage) -> None:
        self.page = page
        self.calls: list[dict[str, object]] = []

    def list_owned(self, **kwargs: object) -> ConversationSummaryPage:
        self.calls.append(kwargs)
        return self.page


def _summary(conversation_id: UUID, updated_day: int) -> ConversationSummary:
    timestamp = datetime(2025, 1, updated_day, tzinfo=timezone.utc)
    return ConversationSummary(
        id=conversation_id,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _client(
    access_port: FakeConversationAccessPort,
    summaries: FakeConversationListReadService,
    principal: RequestPrincipal,
) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_conversation_access_service] = lambda: (
        ConversationAccessService(access_port)  # type: ignore[arg-type]
    )
    application.dependency_overrides[get_conversation_list_read_service] = lambda: summaries
    application.dependency_overrides[get_request_principal] = lambda: principal
    return TestClient(application)


def test_list_http_returns_only_safe_summary_fields_and_cursor() -> None:
    next_cursor = ConversationListCursor(
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        id=CONVERSATION_TWO,
    )
    summaries = FakeConversationListReadService(
        ConversationSummaryPage(
            conversations=(
                _summary(CONVERSATION_ONE, 3),
                _summary(CONVERSATION_TWO, 1),
            ),
            has_more=True,
            next_cursor=next_cursor,
        )
    )
    access_port = FakeConversationAccessPort(
        {UUID("00000000-0000-0000-0000-000000000223"): Conversation(owner_subject="other")}
    )

    response = _client(
        access_port,
        summaries,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get("/api/v1/conversations?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"conversations", "has_more", "next_cursor"}
    assert [item["id"] for item in payload["conversations"]] == [
        str(CONVERSATION_ONE),
        str(CONVERSATION_TWO),
    ]
    assert set(payload["conversations"][0]) == {
        "id",
        "created_at",
        "updated_at",
        "topic_summary",
        "is_pinned",
    }
    assert payload["has_more"] is True
    assert payload["next_cursor"]
    assert decode_conversation_cursor(payload["next_cursor"]) == next_cursor
    assert "owner_subject" not in response.text
    assert "messages" not in response.text
    assert summaries.calls[0]["owner_subject"] == "current-user"
    assert summaries.calls[0]["limit"] == 2


def test_list_http_forwards_cursor_and_returns_empty_page() -> None:
    cursor = ConversationListCursor(
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        id=CONVERSATION_TWO,
    )
    summaries = FakeConversationListReadService(
        ConversationSummaryPage(conversations=(), has_more=False, next_cursor=None)
    )
    access_port = FakeConversationAccessPort()
    client = _client(
        access_port,
        summaries,
        RequestPrincipal(subject="current-user", authenticated=True),
    )

    from app.interfaces.http.conversation_cursor import encode_conversation_cursor

    response = client.get(
        "/api/v1/conversations?cursor=" + encode_conversation_cursor(cursor)
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversations": [],
        "has_more": False,
        "next_cursor": None,
    }
    assert summaries.calls[0]["cursor"] == cursor


def test_list_http_rejects_anonymous_principal_before_query() -> None:
    summaries = FakeConversationListReadService(
        ConversationSummaryPage(conversations=(), has_more=False, next_cursor=None)
    )

    response = _client(
        FakeConversationAccessPort(),
        summaries,
        RequestPrincipal.anonymous(),
    ).get("/api/v1/conversations")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CONVERSATION_ACCESS_DENIED"
    assert summaries.calls == []


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "cursor=invalid"])
def test_list_http_rejects_invalid_pagination(query: str) -> None:
    summaries = FakeConversationListReadService(
        ConversationSummaryPage(conversations=(), has_more=False, next_cursor=None)
    )

    response = _client(
        FakeConversationAccessPort(),
        summaries,
        RequestPrincipal(subject="current-user", authenticated=True),
    ).get("/api/v1/conversations?" + query)

    assert response.status_code == 422
    assert summaries.calls == []
