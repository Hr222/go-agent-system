from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest

from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.dialogue.application import (
    StreamingConversationCommand,
    StreamingConversationRuntime,
)
from app.modules.llm.contracts import ChatLlmStreamChunk
from app.modules.security.domain.principal import RequestPrincipal


def _message(
    conversation_id: UUID,
    sequence: int,
    role: MessageRole,
    content: str,
) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=sequence,
    )


class FakeConversationAccess:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.created = []
        self.resolved = []

    def create(self, command):  # noqa: ANN001
        self.created.append(command)
        return self.conversation

    def resolve(self, query):  # noqa: ANN001
        self.resolved.append(query)
        return self.conversation


class FakeConversationWriter:
    def __init__(self, conversation: Conversation, messages=None, *, fail_assistant=False):  # noqa: ANN001
        self.conversation = conversation
        self.messages = list(messages or [])
        self.fail_assistant = fail_assistant

    def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
        assert conversation_id == self.conversation.id
        if role is MessageRole.ASSISTANT and self.fail_assistant:
            raise RuntimeError("助手消息写入失败")
        message = _message(
            conversation_id,
            len(self.messages) + 1,
            role,
            content,
        )
        self.messages.append(message)
        return message


class FakeStream:
    def __init__(self, chunks, error: BaseException | None = None):  # noqa: ANN001
        self.chunks = chunks
        self.error = error
        self.closed = False

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[ChatLlmStreamChunk]:
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error

    async def aclose(self) -> None:
        self.closed = True


class FakeStreamingLlm:
    def __init__(self, stream: FakeStream) -> None:
        self.stream_value = stream
        self.requests = []

    def stream(self, request):  # noqa: ANN001
        self.requests.append(request)
        return self.stream_value


def _runtime(*, chunks, messages=None, error=None, fail_assistant=False):  # noqa: ANN001
    conversation_id = messages[0].conversation_id if messages else uuid4()
    conversation = Conversation(id=conversation_id, owner_subject="user-1")
    access = FakeConversationAccess(conversation)
    writer = FakeConversationWriter(
        conversation,
        messages,
        fail_assistant=fail_assistant,
    )
    model_stream = FakeStream(chunks, error=error)
    llm = FakeStreamingLlm(model_stream)
    runtime = StreamingConversationRuntime(
        conversation_access=access,  # type: ignore[arg-type]
        conversation_writer=writer,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )
    return runtime, access, writer, llm, model_stream


def _command(conversation_id: UUID | None = None) -> StreamingConversationCommand:
    return StreamingConversationCommand(
        principal=RequestPrincipal(subject="user-1", authenticated=True),
        message="  本轮问题  ",
        conversation_id=conversation_id,
    )


def test_runtime_creates_conversation_and_persists_complete_messages() -> None:
    runtime, access, writer, llm, _ = _runtime(
        chunks=[
            ChatLlmStreamChunk(content="本轮"),
            ChatLlmStreamChunk(
                content="回答",
                model="glm-test",
                prompt_version="streaming-test-v1",
                total_tokens=9,
            ),
        ]
    )

    async def scenario() -> list[object]:
        stream = await runtime.execute(_command())
        return [event async for event in stream]

    events = asyncio.run(scenario())

    assert [event.kind for event in events] == [
        "started",
        "delta",
        "delta",
        "completed",
    ]
    assert events[0].conversation_id == writer.conversation.id
    assert [message.role for message in writer.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert [message.content for message in writer.messages] == ["本轮问题", "本轮回答"]
    assert access.created[0].principal.subject == "user-1"
    assert llm.requests[0].user_prompt == "本轮问题"
    assert llm.requests[0].history_messages == ()
    assert events[-1].result is not None
    assert events[-1].result.assistant_message.content == "本轮回答"


def test_runtime_resolves_existing_conversation_and_appends_in_sequence() -> None:
    conversation_id = uuid4()
    history = [
        _message(conversation_id, 1, MessageRole.USER, "旧问题"),
        _message(conversation_id, 2, MessageRole.ASSISTANT, "旧回答"),
    ]
    runtime, access, writer, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="新回答")],
        messages=history,
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command(conversation_id))
        [event async for event in stream]

    asyncio.run(scenario())

    assert access.created == []
    assert access.resolved[0].conversation_id == conversation_id
    assert [message.sequence for message in writer.messages] == [1, 2, 3, 4]
    assert [message.role for message in writer.messages[-2:]] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]


@pytest.mark.parametrize(
    "error",
    [RuntimeError("上游失败"), asyncio.CancelledError()],
)
def test_runtime_keeps_user_when_stream_does_not_complete(error: BaseException) -> None:
    runtime, _, writer, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="部分回答")],
        error=error,
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        with pytest.raises(type(error)):
            [event async for event in stream]

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]


def test_runtime_keeps_user_when_answer_is_empty() -> None:
    runtime, _, writer, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="  "), ChatLlmStreamChunk(content="")]
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        with pytest.raises(RuntimeError, match="空响应"):
            [event async for event in stream]

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]


def test_runtime_keeps_user_when_assistant_write_fails() -> None:
    runtime, _, writer, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="回答")],
        fail_assistant=True,
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        with pytest.raises(RuntimeError, match="助手消息写入失败"):
            [event async for event in stream]

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]


def test_runtime_closes_model_stream_when_consumer_stops_early() -> None:
    runtime, _, writer, _, model_stream = _runtime(
        chunks=[ChatLlmStreamChunk(content="部分回答"), ChatLlmStreamChunk(content="不会保存")]
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        await anext(stream)
        await anext(stream)
        await stream.aclose()

    asyncio.run(scenario())

    assert model_stream.closed is True
    assert [message.role for message in writer.messages] == [MessageRole.USER]
