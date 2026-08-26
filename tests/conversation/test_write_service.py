from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.platform.conversation.application import ConversationWriteService
from app.platform.conversation.domain import Conversation, Message, MessageRole


class FakeConversationWritePort:
    def __init__(self) -> None:
        self.conversations: list[Conversation] = []
        self.messages: list[Message] = []

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self.conversations.append(conversation)
        return conversation

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=len(self.messages) + 1,
        )
        self.messages.append(message)
        return message


def test_create_conversation_returns_isolated_persisted_conversations() -> None:
    port = FakeConversationWritePort()
    service = ConversationWriteService(port)

    first = service.create_conversation(owner_subject="user-1")
    second = service.create_conversation(owner_subject="user-2")

    assert first.id != second.id
    assert [conversation.owner_subject for conversation in port.conversations] == [
        "user-1",
        "user-2",
    ]
    assert port.conversations == [first, second]


def test_append_message_passes_normalized_role_and_preserves_content() -> None:
    port = FakeConversationWritePort()
    service = ConversationWriteService(port)
    conversation_id = uuid4()

    message = service.append_message(
        conversation_id=conversation_id,
        role="user",
        content="  原始内容  ",
    )

    assert message.conversation_id == conversation_id
    assert message.role is MessageRole.USER
    assert message.content == "  原始内容  "
    assert message.sequence == 1


@pytest.mark.parametrize(
    ("role", "content"),
    [("tool", "内容"), ("user", "   "), (None, "内容")],
)
def test_append_message_rejects_invalid_input_without_port_call(
    role: object,
    content: str,
) -> None:
    port = FakeConversationWritePort()
    service = ConversationWriteService(port)

    with pytest.raises(ValueError):
        service.append_message(
            conversation_id=uuid4(),
            role=role,  # type: ignore[arg-type]
            content=content,
        )

    assert port.messages == []


def test_append_message_rejects_non_uuid_conversation_without_port_call() -> None:
    port = FakeConversationWritePort()
    service = ConversationWriteService(port)

    with pytest.raises(ValueError, match="会话标识必须是 UUID"):
        service.append_message(
            conversation_id="not-a-uuid",  # type: ignore[arg-type]
            role=MessageRole.USER,
            content="内容",
        )

    assert port.messages == []
