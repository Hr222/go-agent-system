from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.platform.conversation.application import (
    ConversationWriteService,
    RuleBasedConversationTopicSummaryGenerator,
)
from app.platform.conversation.domain import Conversation, Message, MessageRole


class FakeTopicGenerator:
    def __init__(self, value: str | None = None, error: Exception | None = None) -> None:
        self.value = value
        self.error = error
        self.messages: list[str] = []

    def generate(self, message: str) -> str | None:
        self.messages.append(message)
        if self.error is not None:
            raise self.error
        return self.value


class FakeWritePort:
    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.topic_summary: str | None = None
        self.topic_updates: list[str] = []

    def save_conversation(self, conversation: Conversation) -> Conversation:
        return conversation

    def append_message(self, *, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=len(self.messages) + 1,
        )
        self.messages.append(message)
        return message

    def update_topic_summary(
        self, *, conversation_id: UUID, topic_summary: str | None
    ) -> Conversation:
        self.topic_summary = topic_summary
        return Conversation(id=conversation_id, owner_subject="user-1", topic_summary=topic_summary)

    def update_topic_summary_if_empty(
        self, *, conversation_id: UUID, topic_summary: str
    ) -> Conversation | None:
        if self.topic_summary is not None:
            return None
        self.topic_summary = topic_summary
        self.topic_updates.append(topic_summary)
        return Conversation(id=conversation_id, owner_subject="user-1", topic_summary=topic_summary)


def test_rule_generator_normalizes_first_sentence_and_truncates() -> None:
    generator = RuleBasedConversationTopicSummaryGenerator()

    result = generator.generate("  讨论采购方案。这里是后续细节\n和更多说明。 ")

    assert result == "讨论采购方案"
    assert len(generator.generate("长" * 100) or "") == 80


@pytest.mark.parametrize("value", [None, "", "   "])
def test_rule_generator_returns_none_for_blank_message(value: str | None) -> None:
    assert RuleBasedConversationTopicSummaryGenerator().generate(value or "") is None


def test_first_user_message_generates_summary_without_affecting_message_write() -> None:
    port = FakeWritePort()
    generator = FakeTopicGenerator(value="首轮话题")
    service = ConversationWriteService(port, topic_summary_generator=generator)

    message = service.append_message(
        conversation_id=uuid4(),
        role=MessageRole.USER,
        content="首条消息",
    )

    assert message.sequence == 1
    assert port.topic_summary == "首轮话题"
    assert generator.messages == ["首条消息"]


def test_generator_failure_falls_back_and_does_not_raise() -> None:
    port = FakeWritePort()
    service = ConversationWriteService(
        port,
        topic_summary_generator=FakeTopicGenerator(error=RuntimeError("不可用")),
    )

    service.append_message(
        conversation_id=uuid4(),
        role=MessageRole.USER,
        content="  使用首条消息回退  ",
    )

    assert port.topic_summary == "使用首条消息回退"


def test_follow_up_message_and_existing_summary_are_not_overwritten() -> None:
    port = FakeWritePort()
    generator = FakeTopicGenerator(value="自动标题")
    service = ConversationWriteService(port, topic_summary_generator=generator)
    conversation_id = uuid4()

    service.append_message(conversation_id=conversation_id, role=MessageRole.USER, content="首条")
    service.append_message(conversation_id=conversation_id, role=MessageRole.USER, content="后续")

    assert port.topic_summary == "自动标题"
    assert port.topic_updates == ["自动标题"]
    assert generator.messages == ["首条"]
