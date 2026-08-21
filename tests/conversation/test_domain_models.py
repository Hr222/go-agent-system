from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.modules.conversation.domain import Conversation, Message, MessageRole


def test_conversation_generates_uuid_and_utc_timestamps() -> None:
    conversation = Conversation(owner_subject=" user-1 ")

    assert isinstance(conversation.id, UUID)
    assert conversation.owner_subject == "user-1"
    assert conversation.created_at.tzinfo is timezone.utc
    assert conversation.updated_at.tzinfo is timezone.utc


@pytest.mark.parametrize("owner_subject", [None, "", "   ", 1])
def test_conversation_rejects_invalid_owner_subject(owner_subject: object) -> None:
    with pytest.raises(ValueError, match="归属主体"):
        Conversation(owner_subject=owner_subject)  # type: ignore[arg-type]


def test_message_preserves_valid_fields() -> None:
    message_id = uuid4()
    conversation_id = uuid4()
    created_at = datetime(2026, 8, 18, 9, 30, tzinfo=timezone.utc)

    message = Message(
        id=message_id,
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="  保留原始内容  ",
        sequence=1,
        created_at=created_at,
    )

    assert message.id == message_id
    assert message.conversation_id == conversation_id
    assert message.role is MessageRole.USER
    assert message.content == "  保留原始内容  "
    assert message.sequence == 1
    assert message.created_at == created_at


@pytest.mark.parametrize("role", ["user", "tool", None])
def test_message_rejects_invalid_roles(role: object) -> None:
    with pytest.raises(ValueError, match="消息角色无效"):
        Message(
            conversation_id=uuid4(),
            role=role,  # type: ignore[arg-type]
            content="内容",
            sequence=1,
        )


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_message_rejects_blank_content(content: str) -> None:
    with pytest.raises(ValueError, match="消息内容不能为空"):
        Message(
            conversation_id=uuid4(),
            role=MessageRole.USER,
            content=content,
            sequence=1,
        )


@pytest.mark.parametrize("sequence", [0, -1, True, 1.0])
def test_message_rejects_non_positive_or_non_integer_sequence(sequence: object) -> None:
    with pytest.raises(ValueError, match="消息顺序号必须是正整数"):
        Message(
            conversation_id=uuid4(),
            role=MessageRole.ASSISTANT,
            content="内容",
            sequence=sequence,  # type: ignore[arg-type]
        )
