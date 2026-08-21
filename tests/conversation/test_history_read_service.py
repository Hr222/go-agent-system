from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.modules.conversation.application import ConversationHistoryReadService
from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.conversation.ports import (
    DEFAULT_HISTORY_PAGE_SIZE,
    ConversationHistoryPage,
)


class FakeConversationReadPort:
    def __init__(self, page: ConversationHistoryPage) -> None:
        self.page = page
        self.calls: list[dict[str, object]] = []

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage:
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "limit": limit,
                "after_sequence": after_sequence,
            }
        )
        return self.page


def _empty_page() -> ConversationHistoryPage:
    return ConversationHistoryPage(
        conversation=Conversation(owner_subject="user-1"),
        messages=(),
        has_more=False,
        next_after_sequence=None,
    )


def test_history_read_service_uses_default_page_size_and_preserves_result() -> None:
    port = FakeConversationReadPort(_empty_page())
    service = ConversationHistoryReadService(port)
    conversation_id = uuid4()

    result = service.read_history(conversation_id=conversation_id)

    assert result.messages == ()
    assert port.calls == [
        {
            "conversation_id": conversation_id,
            "limit": DEFAULT_HISTORY_PAGE_SIZE,
            "after_sequence": None,
        }
    ]


@pytest.mark.parametrize("limit", [0, 201, True, 1.0])
def test_history_read_service_rejects_invalid_page_size(limit: object) -> None:
    port = FakeConversationReadPort(_empty_page())

    with pytest.raises(ValueError, match="历史页大小"):
        ConversationHistoryReadService(port).read_history(
            conversation_id=uuid4(),
            limit=limit,  # type: ignore[arg-type]
        )

    assert port.calls == []


@pytest.mark.parametrize("after_sequence", [0, -1, True, 1.0])
def test_history_read_service_rejects_invalid_cursor(after_sequence: object) -> None:
    port = FakeConversationReadPort(_empty_page())

    with pytest.raises(ValueError, match="历史游标"):
        ConversationHistoryReadService(port).read_history(
            conversation_id=uuid4(),
            after_sequence=after_sequence,  # type: ignore[arg-type]
        )

    assert port.calls == []


def test_history_read_service_rejects_non_uuid_conversation() -> None:
    port = FakeConversationReadPort(_empty_page())

    with pytest.raises(ValueError, match="会话标识必须是 UUID"):
        ConversationHistoryReadService(port).read_history(
            conversation_id="not-a-uuid",  # type: ignore[arg-type]
        )

    assert port.calls == []


def test_history_page_can_carry_ordered_domain_messages() -> None:
    conversation = Conversation(owner_subject="user-1")
    messages = (
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="第一条",
            sequence=1,
        ),
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="第二条",
            sequence=2,
        ),
    )

    page = ConversationHistoryPage(
        conversation=conversation,
        messages=messages,
        has_more=False,
        next_after_sequence=None,
    )

    assert [message.sequence for message in page.messages] == [1, 2]
