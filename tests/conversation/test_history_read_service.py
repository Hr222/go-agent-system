from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.platform.conversation.application import ConversationHistoryReadService
from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.ports import (
    DEFAULT_HISTORY_PAGE_SIZE,
    ConversationHistoryPage,
    ConversationRecentMessageWindow,
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


class FakeRecentMessageReadPort:
    def __init__(self, window: ConversationRecentMessageWindow) -> None:
        self.window = window
        self.calls: list[dict[str, object]] = []

    def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow:
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "through_sequence": through_sequence,
                "limit": limit,
            }
        )
        return self.window


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


def test_recent_message_read_service_passes_valid_snapshot_parameters() -> None:
    from app.platform.conversation.application import ConversationRecentMessageReadService

    conversation = Conversation(owner_subject="user-1")
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="当前问题",
        sequence=3,
    )
    port = FakeRecentMessageReadPort(
        ConversationRecentMessageWindow(
            conversation_id=conversation.id,
            messages=(message,),
        )
    )

    result = ConversationRecentMessageReadService(port).read_recent_messages(
        conversation_id=conversation.id,
        through_sequence=3,
        limit=20,
    )

    assert result.messages == (message,)
    assert port.calls == [
        {
            "conversation_id": conversation.id,
            "through_sequence": 3,
            "limit": 20,
        }
    ]


@pytest.mark.parametrize("through_sequence", [0, -1, True, 1.0])
def test_recent_message_read_service_rejects_invalid_sequence_boundary(
    through_sequence: object,
) -> None:
    from app.platform.conversation.application import ConversationRecentMessageReadService

    conversation_id = uuid4()
    port = FakeRecentMessageReadPort(
        ConversationRecentMessageWindow(conversation_id=conversation_id, messages=())
    )

    with pytest.raises(ValueError, match="截止顺序号"):
        ConversationRecentMessageReadService(port).read_recent_messages(
            conversation_id=conversation_id,
            through_sequence=through_sequence,  # type: ignore[arg-type]
        )

    assert port.calls == []


@pytest.mark.parametrize("limit", [0, 201, True, 1.0])
def test_recent_message_read_service_rejects_invalid_window_limit(limit: object) -> None:
    from app.platform.conversation.application import ConversationRecentMessageReadService

    conversation_id = uuid4()
    port = FakeRecentMessageReadPort(
        ConversationRecentMessageWindow(conversation_id=conversation_id, messages=())
    )

    with pytest.raises(ValueError, match="数量上限"):
        ConversationRecentMessageReadService(port).read_recent_messages(
            conversation_id=conversation_id,
            through_sequence=1,
            limit=limit,  # type: ignore[arg-type]
        )

    assert port.calls == []


def test_recent_message_read_service_rejects_window_from_another_conversation() -> None:
    from app.platform.conversation.application import ConversationRecentMessageReadService

    conversation_id = uuid4()
    port = FakeRecentMessageReadPort(
        ConversationRecentMessageWindow(conversation_id=uuid4(), messages=())
    )

    with pytest.raises(ValueError, match="其他会话"):
        ConversationRecentMessageReadService(port).read_recent_messages(
            conversation_id=conversation_id,
            through_sequence=1,
        )

    assert len(port.calls) == 1
