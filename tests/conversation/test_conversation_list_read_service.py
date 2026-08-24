from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.modules.conversation.application import ConversationListReadService
from app.modules.conversation.ports import (
    ConversationListCursor,
    ConversationSummary,
    ConversationSummaryPage,
)


class FakeConversationListReadPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_owned(self, **kwargs: object) -> ConversationSummaryPage:
        self.calls.append(kwargs)
        return ConversationSummaryPage(conversations=(), has_more=False, next_cursor=None)


def test_list_service_normalizes_owner_and_forwards_page_arguments() -> None:
    port = FakeConversationListReadPort()
    cursor = ConversationListCursor(
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        id=UUID("00000000-0000-0000-0000-000000000201"),
    )

    result = ConversationListReadService(port).list_owned(
        owner_subject=" current-user ",
        limit=20,
        cursor=cursor,
    )

    assert result.conversations == ()
    assert port.calls == [
        {
            "owner_subject": "current-user",
            "limit": 20,
            "cursor": cursor,
        }
    ]


@pytest.mark.parametrize("limit", [0, 201, True, 1.0])
def test_list_service_rejects_invalid_limit_without_querying(limit: object) -> None:
    port = FakeConversationListReadPort()

    with pytest.raises(ValueError, match="会话列表页大小"):
        ConversationListReadService(port).list_owned(
            owner_subject="current-user",
            limit=limit,  # type: ignore[arg-type]
        )

    assert port.calls == []


def test_list_service_rejects_missing_owner_without_querying() -> None:
    port = FakeConversationListReadPort()

    with pytest.raises(ValueError, match="会话列表主体"):
        ConversationListReadService(port).list_owned(owner_subject="  ")

    assert port.calls == []


def test_summary_page_keeps_only_minimum_summary_fields() -> None:
    summary = ConversationSummary(
        id=UUID("00000000-0000-0000-0000-000000000202"),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )
    page = ConversationSummaryPage(
        conversations=(summary,),
        has_more=False,
        next_cursor=None,
    )

    assert page.conversations == (summary,)
