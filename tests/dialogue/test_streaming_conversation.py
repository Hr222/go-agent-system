from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from openai import APITimeoutError

from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.platform.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationContextBuilder,
)
from app.platform.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Conversation,
    Message,
    MessageRole,
)
from app.platform.conversation.errors import (
    ContextBudgetExceededError,
    ConversationAccessDeniedError,
)
from app.platform.conversation.ports import ConversationHistoryPage, ConversationRecentMessageWindow
from app.platform.dialogue.application import (
    ConversationTurnCoordinator,
    StreamingConversationCommand,
    StreamingConversationRuntime,
    ThreadedStreamingConversationPersistence,
)
from app.platform.llm.contracts import ChatLlmStreamChunk
from app.platform.security.domain.principal import RequestPrincipal
from app.shared.config import Settings


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
    def __init__(
        self,
        conversation: Conversation,
        *,
        resolve_error: BaseException | None = None,
    ) -> None:
        self.conversation = conversation
        self.resolve_error = resolve_error
        self.created = []
        self.resolved = []

    def create(self, command):  # noqa: ANN001
        self.created.append(command)
        return self.conversation

    def resolve(self, query):  # noqa: ANN001
        self.resolved.append(query)
        if self.resolve_error is not None:
            raise self.resolve_error
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


class FakeConversationReader:
    def __init__(
        self,
        writer: FakeConversationWriter,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.writer = writer
        self.error = error
        self.calls: list[tuple[int, int | None]] = []

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage:
        self.calls.append((limit, after_sequence))
        if self.error is not None:
            raise self.error
        if conversation_id != self.writer.conversation.id:
            raise RuntimeError("会话不存在")

        records = [
            message
            for message in self.writer.messages
            if after_sequence is None or message.sequence > after_sequence
        ]
        page_messages = tuple(records[:limit])
        has_more = len(records) > limit
        return ConversationHistoryPage(
            conversation=self.writer.conversation,
            messages=page_messages,
            has_more=has_more,
            next_after_sequence=page_messages[-1].sequence if has_more else None,
        )

    def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow:
        self.calls.append((limit, through_sequence))
        if self.error is not None:
            raise self.error
        if conversation_id != self.writer.conversation.id:
            raise RuntimeError("会话不存在")
        records = [
            message
            for message in self.writer.messages
            if message.sequence <= through_sequence
        ]
        return ConversationRecentMessageWindow(
            conversation_id=conversation_id,
            messages=tuple(records[-limit:]),
        )


class FakeStreamingConversationPersistence:
    """测试用异步端口，复现 Runtime 与同步数据库的隔离边界。"""

    def __init__(self, access, writer, reader) -> None:  # noqa: ANN001
        self.access = access
        self.writer = writer
        self.reader = reader

    async def create_conversation(self, *, principal):  # noqa: ANN001
        return self.access.create(type("Command", (), {"principal": principal})())

    async def resolve_conversation(self, *, principal, conversation_id):  # noqa: ANN001
        return self.access.resolve(
            type(
                "Query",
                (),
                {"principal": principal, "conversation_id": conversation_id},
            )()
        )

    async def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
        return self.writer.append_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

    async def read_recent_messages(
        self,
        *,
        conversation_id,
        through_sequence,
        limit,
    ):  # noqa: ANN001
        return self.reader.read_recent_messages(
            conversation_id=conversation_id,
            through_sequence=through_sequence,
            limit=limit,
        )


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


class RetryBeforeActivityChatModel:
    def __init__(self) -> None:
        self.attempts = 0

    def bind(self, **kwargs: object) -> "RetryBeforeActivityChatModel":
        del kwargs
        return self

    def astream(self, messages: object):  # noqa: ANN201
        del messages
        self.attempts += 1
        attempt = self.attempts

        async def generate():
            if attempt == 1:
                request = httpx.Request(
                    "POST",
                    "https://provider.example.com/v1/chat/completions",
                )
                raise APITimeoutError(request=request)
            yield type(
                "Message",
                (),
                {
                    "content": "重试后的完整回答",
                    "usage_metadata": {},
                    "response_metadata": {},
                },
            )()

        return generate()


def _runtime(
    *,
    chunks,
    messages=None,
    error=None,
    fail_assistant=False,
    reader_error=None,
    resolve_error=None,
    context_policy=ContextPolicy(max_messages=20),
    context_budget=ContextBudget(max_cost=12_000),
    coordinator: ConversationTurnCoordinator | None = None,
):  # noqa: ANN001
    conversation_id = messages[0].conversation_id if messages else uuid4()
    conversation = Conversation(id=conversation_id, owner_subject="user-1")
    access = FakeConversationAccess(conversation, resolve_error=resolve_error)
    writer = FakeConversationWriter(
        conversation,
        messages,
        fail_assistant=fail_assistant,
    )
    reader = FakeConversationReader(writer, error=reader_error)
    persistence = FakeStreamingConversationPersistence(access, writer, reader)
    model_stream = FakeStream(chunks, error=error)
    llm = FakeStreamingLlm(model_stream)
    runtime = StreamingConversationRuntime(
        conversation_persistence=persistence,  # type: ignore[arg-type]
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=llm,  # type: ignore[arg-type]
        context_policy=context_policy,
        context_budget=context_budget,
        conversation_turn_coordinator=coordinator or ConversationTurnCoordinator(),
    )
    return runtime, access, writer, reader, llm, model_stream


def _command(conversation_id: UUID | None = None) -> StreamingConversationCommand:
    return StreamingConversationCommand(
        principal=RequestPrincipal(subject="user-1", authenticated=True),
        message="  本轮问题  ",
        conversation_id=conversation_id,
    )


def test_runtime_creates_conversation_and_persists_complete_messages() -> None:
    runtime, access, writer, reader, llm, _ = _runtime(
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
    assert reader.calls == [(20, 1)]
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
    runtime, access, writer, _, llm, _ = _runtime(
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
    assert [
        (message.role.value, message.content)
        for message in llm.requests[0].history_messages
    ] == [
        ("user", "旧问题"),
        ("assistant", "旧回答"),
    ]
    assert llm.requests[0].user_prompt == "本轮问题"


def test_runtime_reads_history_across_pages_and_keeps_latest_context_window() -> None:
    conversation_id = uuid4()
    history = [
        _message(
            conversation_id,
            sequence,
            MessageRole.USER if sequence % 2 else MessageRole.ASSISTANT,
            f"消息 {sequence}",
        )
        for sequence in range(1, 206)
    ]
    runtime, _, _, reader, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="回答")],
        messages=history,
        context_policy=ContextPolicy(max_messages=3),
        context_budget=ContextBudget(max_cost=100),
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command(conversation_id))
        [event async for event in stream]

    asyncio.run(scenario())

    assert reader.calls == [(3, 206)]
    assert [message.content for message in llm.requests[0].history_messages] == [
        "消息 204",
        "消息 205",
    ]
    assert llm.requests[0].user_prompt == "本轮问题"


@pytest.mark.parametrize(
    "error",
    [RuntimeError("上游失败"), asyncio.CancelledError()],
)
def test_runtime_keeps_user_when_stream_does_not_complete(error: BaseException) -> None:
    runtime, _, writer, _, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="部分回答")],
        error=error,
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        with pytest.raises(type(error)):
            [event async for event in stream]

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]


def test_runtime_cancellation_waits_for_user_worker_before_releasing_turn_lease() -> None:
    conversation = Conversation(owner_subject="user-1")

    class Worker:
        def __init__(self, index: int, factory: "Factory") -> None:
            self.index = index
            self.factory = factory
            self.closed = False

        def create_conversation(self, *, principal):  # noqa: ANN001
            del principal
            return conversation

        def resolve_conversation(self, *, principal, conversation_id):  # noqa: ANN001
            del principal, conversation_id
            return conversation

        def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
            if role is MessageRole.USER:
                self.factory.user_worker_started.set()
                self.factory.release_user_worker.wait(timeout=2)
            return _message(
                conversation_id,
                1,
                role,
                content,
            )

        def read_recent_messages(
            self,
            *,
            conversation_id,
            through_sequence,
            limit,
        ):  # noqa: ANN001
            del through_sequence, limit
            return ConversationRecentMessageWindow(
                conversation_id=conversation_id,
                messages=(),
            )

        def close(self) -> None:
            self.closed = True

    class Factory:
        def __init__(self) -> None:
            self.user_worker_started = Event()
            self.release_user_worker = Event()
            self.workers: list[Worker] = []

        def create(self) -> Worker:
            worker = Worker(len(self.workers), self)
            self.workers.append(worker)
            return worker

    factory = Factory()
    coordinator = ConversationTurnCoordinator()
    persistence = ThreadedStreamingConversationPersistence(factory)  # type: ignore[arg-type]
    runtime = StreamingConversationRuntime(
        conversation_persistence=persistence,  # type: ignore[arg-type]
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=object(),  # type: ignore[arg-type]
        conversation_turn_coordinator=coordinator,
    )

    async def scenario() -> None:
        operation = asyncio.create_task(runtime.execute(_command()))
        assert await asyncio.to_thread(factory.user_worker_started.wait, 1)
        operation.cancel()
        factory.release_user_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())

    assert len(factory.workers) == 2
    assert all(worker.closed for worker in factory.workers)
    assert coordinator.tracked_conversation_count == 0


def test_runtime_keeps_user_when_answer_is_empty() -> None:
    runtime, _, writer, _, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="  "), ChatLlmStreamChunk(content="")]
    )

    async def scenario() -> None:
        stream = await runtime.execute(_command())
        with pytest.raises(RuntimeError, match="空响应"):
            [event async for event in stream]

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]


def test_runtime_keeps_user_when_assistant_write_fails() -> None:
    runtime, _, writer, _, _, _ = _runtime(
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
    runtime, _, writer, _, _, model_stream = _runtime(
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


def test_runtime_keeps_user_when_context_budget_is_exceeded() -> None:
    runtime, _, writer, _, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="不会调用")],
        context_budget=ContextBudget(max_cost=1),
    )

    async def scenario() -> None:
        with pytest.raises(ContextBudgetExceededError, match="最新上下文消息"):
            await runtime.execute(_command())

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]
    assert llm.requests == []


def test_runtime_keeps_user_when_history_read_fails() -> None:
    runtime, _, writer, _, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="不会调用")],
        reader_error=RuntimeError("数据库不可用"),
    )

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="数据库不可用"):
            await runtime.execute(_command())

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [MessageRole.USER]
    assert llm.requests == []


def test_runtime_rejects_inaccessible_conversation_before_reading_history() -> None:
    conversation_id = uuid4()
    runtime, access, writer, reader, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="不会调用")],
        messages=[_message(conversation_id, 1, MessageRole.USER, "旧问题")],
        resolve_error=ConversationAccessDeniedError("会话不可用。"),
    )

    async def scenario() -> None:
        with pytest.raises(ConversationAccessDeniedError, match="会话不可用"):
            await runtime.execute(_command(conversation_id))

    asyncio.run(scenario())

    assert len(access.resolved) == 1
    assert reader.calls == []
    assert [message.content for message in writer.messages] == ["旧问题"]
    assert llm.requests == []


def test_runtime_persists_one_turn_when_adapter_retries_before_activity() -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-test",
        llm_retry_base_backoff_seconds=0.01,
    )
    waits: list[float] = []

    async def record_sleep(delay: float) -> None:
        waits.append(delay)

    model = RetryBeforeActivityChatModel()
    llm = LangChainGlmChatLlm(
        configuration=configuration,
        chat_model=model,
        retry_policy=LlmTransientRetryPolicy(
            provider="glm",
            configuration=configuration,
            async_sleep_fn=record_sleep,
            random_fn=lambda: 0.0,
            clock=lambda: 1.0,
        ),
    )
    conversation = Conversation(id=uuid4(), owner_subject="user-1")
    access = FakeConversationAccess(conversation)
    writer = FakeConversationWriter(conversation)
    reader = FakeConversationReader(writer)
    runtime = StreamingConversationRuntime(
        conversation_persistence=FakeStreamingConversationPersistence(access, writer, reader),  # type: ignore[arg-type]
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=llm,
        conversation_turn_coordinator=ConversationTurnCoordinator(),
    )

    async def scenario() -> list[object]:
        stream = await runtime.execute(_command())
        return [event async for event in stream]

    events = asyncio.run(scenario())

    assert [event.kind for event in events] == ["started", "delta", "completed"]
    assert model.attempts == 2
    assert waits == [0.01]
    assert [message.role for message in writer.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert [message.content for message in writer.messages] == [
        "本轮问题",
        "重试后的完整回答",
    ]


def test_runtime_serializes_same_conversation_until_assistant_is_persisted() -> None:
    coordinator = ConversationTurnCoordinator()
    runtime, _, writer, reader, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="第一轮回答")],
        coordinator=coordinator,
    )
    command = _command(writer.conversation.id)

    async def scenario() -> None:
        first_stream = await runtime.execute(command)
        assert (await anext(first_stream)).kind == "started"
        assert (await anext(first_stream)).kind == "delta"

        waiting_second_stream = asyncio.create_task(runtime.execute(command))
        await asyncio.sleep(0)

        assert not waiting_second_stream.done()
        assert [message.role for message in writer.messages] == [MessageRole.USER]
        assert len(reader.calls) == 1
        assert len(llm.requests) == 1

        [event async for event in first_stream]
        second_stream = await waiting_second_stream

        assert [message.role for message in writer.messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
            MessageRole.USER,
        ]
        assert len(reader.calls) == 2

        assert (await anext(second_stream)).kind == "started"
        assert (await anext(second_stream)).kind == "delta"
        [event async for event in second_stream]

    asyncio.run(scenario())

    assert [
        (message.role.value, message.content)
        for message in llm.requests[1].history_messages
    ] == [("user", "本轮问题"), ("assistant", "第一轮回答")]
    assert coordinator.tracked_conversation_count == 0


def test_runtime_allows_different_conversations_to_start_in_parallel() -> None:
    coordinator = ConversationTurnCoordinator()
    first_runtime, _, _, _, first_llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="第一轮回答")],
        coordinator=coordinator,
    )
    second_runtime, _, _, _, second_llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="第二轮回答")],
        coordinator=coordinator,
    )

    async def scenario() -> None:
        first_stream, second_stream = await asyncio.gather(
            first_runtime.execute(_command()),
            second_runtime.execute(_command()),
        )
        first_started, second_started = await asyncio.gather(
            anext(first_stream),
            anext(second_stream),
        )
        assert first_started.kind == "started"
        assert second_started.kind == "started"

        first_delta, second_delta = await asyncio.gather(
            anext(first_stream),
            anext(second_stream),
        )
        assert first_delta.kind == "delta"
        assert second_delta.kind == "delta"
        assert coordinator.tracked_conversation_count == 2

        await asyncio.gather(first_stream.aclose(), second_stream.aclose())

    asyncio.run(scenario())

    assert len(first_llm.requests) == 1
    assert len(second_llm.requests) == 1
    assert coordinator.tracked_conversation_count == 0


@pytest.mark.parametrize(
    "error",
    [RuntimeError("上游失败"), asyncio.CancelledError()],
)
def test_runtime_releases_same_conversation_after_provider_failure_or_cancellation(
    error: BaseException,
) -> None:
    coordinator = ConversationTurnCoordinator()
    runtime, _, writer, _, _, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="部分回答")],
        error=error,
        coordinator=coordinator,
    )
    command = _command(writer.conversation.id)

    async def scenario() -> None:
        first_stream = await runtime.execute(command)
        assert (await anext(first_stream)).kind == "started"
        waiting_second_stream = asyncio.create_task(runtime.execute(command))
        await asyncio.sleep(0)

        assert not waiting_second_stream.done()
        with pytest.raises(type(error)):
            [event async for event in first_stream]

        second_stream = await waiting_second_stream
        assert [message.role for message in writer.messages] == [
            MessageRole.USER,
            MessageRole.USER,
        ]
        await second_stream.aclose()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_runtime_releases_lease_when_closed_before_first_event() -> None:
    coordinator = ConversationTurnCoordinator()
    runtime, _, writer, _, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="不会调用")],
        coordinator=coordinator,
    )
    command = _command(writer.conversation.id)

    async def scenario() -> None:
        first_stream = await runtime.execute(command)
        await first_stream.aclose()

        second_stream = await runtime.execute(command)
        await second_stream.aclose()

    asyncio.run(scenario())

    assert [message.role for message in writer.messages] == [
        MessageRole.USER,
        MessageRole.USER,
    ]
    assert llm.requests == []
    assert coordinator.tracked_conversation_count == 0


def test_runtime_cancellation_while_waiting_does_not_write_a_message() -> None:
    coordinator = ConversationTurnCoordinator()
    runtime, _, writer, reader, llm, _ = _runtime(
        chunks=[ChatLlmStreamChunk(content="不会调用")],
        coordinator=coordinator,
    )
    command = _command(writer.conversation.id)

    async def scenario() -> None:
        first_stream = await runtime.execute(command)
        waiting_second_stream = asyncio.create_task(runtime.execute(command))
        await asyncio.sleep(0)

        waiting_second_stream.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting_second_stream

        assert [message.role for message in writer.messages] == [MessageRole.USER]
        assert len(reader.calls) == 1
        assert llm.requests == []
        await first_stream.aclose()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0
