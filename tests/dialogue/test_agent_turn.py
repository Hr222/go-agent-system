from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Event
from uuid import UUID, uuid4

import pytest

from app.platform.conversation.application import (
    CharacterCountContextMessageCostEstimator,
    ConversationContextBuilder,
)
from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.ports import (
    ConversationHistoryPage,
    ConversationRecentMessageWindow,
)
from app.platform.dialogue.application import (
    ConversationTurnCoordinator,
    DialogueAgentTurnCommand,
    DialogueAgentTurnExecutor,
    DialogueAgentTurnPreparation,
    DialogueAgentTurnRequest,
    DialogueAgentTurnResult,
    StreamingConversationCommand,
    StreamingConversationRuntime,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.platform.llm.contracts import ChatLlmStreamChunk
from app.platform.security.domain.principal import RequestPrincipal


class MemoryConversationAccess:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    def create(self, command):  # noqa: ANN001
        del command
        return self.conversation

    def resolve(self, query):  # noqa: ANN001
        assert query.conversation_id == self.conversation.id
        return self.conversation


class MemoryConversationWriter:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.messages: list[Message] = []

    def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
        assert conversation_id == self.conversation.id
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            sequence=len(self.messages) + 1,
        )
        self.messages.append(message)
        return message


class MemoryConversationReader:
    def __init__(self, writer: MemoryConversationWriter) -> None:
        self.writer = writer
        self.calls = 0

    def read_history(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        after_sequence: int | None,
    ) -> ConversationHistoryPage:
        assert conversation_id == self.writer.conversation.id
        self.calls += 1
        records = [
            message
            for message in self.writer.messages
            if after_sequence is None or message.sequence > after_sequence
        ]
        page_messages = tuple(records[:limit])
        return ConversationHistoryPage(
            conversation=self.writer.conversation,
            messages=page_messages,
            has_more=len(records) > limit,
            next_after_sequence=page_messages[-1].sequence if len(records) > limit else None,
        )

    def read_recent_messages(
        self,
        *,
        conversation_id: UUID,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow:
        assert conversation_id == self.writer.conversation.id
        self.calls += 1
        records = [
            message
            for message in self.writer.messages
            if message.sequence <= through_sequence
        ]
        return ConversationRecentMessageWindow(
            conversation_id=conversation_id,
            messages=tuple(records[-limit:]),
        )


class MemoryStreamingConversationPersistence:
    def __init__(
        self,
        conversation: Conversation,
        writer: MemoryConversationWriter,
        reader: MemoryConversationReader,
    ) -> None:
        self.conversation = conversation
        self.writer = writer
        self.reader = reader

    async def create_conversation(self, *, principal):  # noqa: ANN001
        del principal
        return self.conversation

    async def resolve_conversation(self, *, principal, conversation_id):  # noqa: ANN001
        del principal
        assert conversation_id == self.conversation.id
        return self.conversation

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


class RecordingStreamingLlm:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.requests: list[object] = []

    def stream(self, request):  # noqa: ANN001
        self.requests.append(request)

        async def chunks() -> AsyncIterator[ChatLlmStreamChunk]:
            yield ChatLlmStreamChunk(content=self.answer)

        return chunks()


class BlockingFactWorker:
    """受控地在 worker 线程写入 Agent 结果与续写 assistant 事实。"""

    def __init__(self, writer: MemoryConversationWriter) -> None:
        self.writer = writer
        self.started = Event()
        self.release = Event()
        self.events: list[str] = []
        self.closed = False

    def execute(self, command: DialogueAgentTurnCommand) -> DialogueAgentTurnResult:
        self.started.set()
        if not self.release.wait(timeout=2):
            raise RuntimeError("测试 worker 未被释放。")
        self.events.append("agent_result")
        self.writer.append_message(
            conversation_id=command.conversation_id,
            role=MessageRole.ASSISTANT,
            content="Agent 已完成。",
        )
        return DialogueAgentTurnResult(
            status="completed",
            message="Agent 已完成执行。",
            conversation_id=command.conversation_id,
            execution_result={"artifact": "bid-outline.docx"},
        )

    def close(self) -> None:
        self.closed = True


class BlockingFactWorkerFactory:
    def __init__(self, worker: BlockingFactWorker) -> None:
        self.worker = worker
        self.created = 0

    def create(self) -> BlockingFactWorker:
        self.created += 1
        return self.worker


def _principal() -> RequestPrincipal:
    return RequestPrincipal(subject="user-1", authenticated=True)


def _conversation_runtime(
    *,
    conversation_id: UUID,
    coordinator: ConversationTurnCoordinator,
    answer: str,
) -> tuple[
    StreamingConversationRuntime,
    MemoryConversationWriter,
    MemoryConversationReader,
    RecordingStreamingLlm,
]:
    conversation = Conversation(id=conversation_id, owner_subject="user-1")
    writer = MemoryConversationWriter(conversation)
    reader = MemoryConversationReader(writer)
    persistence = MemoryStreamingConversationPersistence(conversation, writer, reader)
    llm = RecordingStreamingLlm(answer)
    runtime = StreamingConversationRuntime(
        conversation_persistence=persistence,  # type: ignore[arg-type]
        context_builder=ConversationContextBuilder(
            CharacterCountContextMessageCostEstimator()
        ),
        llm=llm,  # type: ignore[arg-type]
        conversation_turn_coordinator=coordinator,
    )
    return runtime, writer, reader, llm


def _agent_turn_request(conversation_id: UUID) -> DialogueAgentTurnRequest:
    principal = _principal()
    call = StructuredAgentCall(
        call_id="call-agent-1",
        capability_code="agent.tender.generate_bid_skeleton",
        conversation_id=str(conversation_id),
        inputs={"file_name": "招标文件.docx"},
    )
    dispatch = ApprovedCapabilityDispatch(
        proposal_id="proposal-agent-1",
        capability_code=call.capability_code,
        dispatch_key="agent.tender.generate_bid_skeleton",
        inputs=dict(call.inputs),
    )
    return DialogueAgentTurnRequest(
        conversation_id=conversation_id,
        confirm=lambda: DialogueAgentTurnPreparation(
            command=DialogueAgentTurnCommand(
                conversation_id=conversation_id,
                capability_code=call.capability_code,
                inputs=dict(call.inputs),
                principal=principal,
                approved_dispatch=dispatch,
                call=call,
            )
        ),
    )


def test_blocking_agent_turn_serializes_same_conversation_but_not_another() -> None:
    coordinator = ConversationTurnCoordinator()
    conversation_id = uuid4()
    runtime, writer, reader, llm = _conversation_runtime(
        conversation_id=conversation_id,
        coordinator=coordinator,
        answer="后续普通回答。",
    )
    other_runtime, other_writer, _other_reader, other_llm = _conversation_runtime(
        conversation_id=uuid4(),
        coordinator=coordinator,
        answer="另一会话回答。",
    )
    worker = BlockingFactWorker(writer)
    factory = BlockingFactWorkerFactory(worker)
    executor = DialogueAgentTurnExecutor(coordinator=coordinator, worker_factory=factory)

    async def scenario() -> None:
        agent_turn = asyncio.create_task(executor.execute(_agent_turn_request(conversation_id)))
        assert await asyncio.to_thread(worker.started.wait, 1)

        waiting_chat = asyncio.create_task(
            runtime.execute(
                StreamingConversationCommand(
                    principal=_principal(),
                    message="请继续说明结果。",
                    conversation_id=conversation_id,
                )
            )
        )
        await asyncio.sleep(0)
        assert not waiting_chat.done()
        assert writer.messages == []
        assert reader.calls == 0
        assert llm.requests == []

        other_stream = await other_runtime.execute(
            StreamingConversationCommand(
                principal=_principal(),
                message="另一会话的问题。",
                conversation_id=other_writer.conversation.id,
            )
        )
        assert (await anext(other_stream)).kind == "started"
        assert (await anext(other_stream)).kind == "delta"
        await other_stream.aclose()
        assert len(other_llm.requests) == 1

        worker.release.set()
        result = await agent_turn
        assert result.status == "completed"

        chat_stream = await waiting_chat
        events = [event async for event in chat_stream]
        assert [event.kind for event in events] == ["started", "delta", "completed"]

    asyncio.run(scenario())

    assert worker.events == ["agent_result"]
    assert worker.closed is True
    assert factory.created == 1
    assert [(message.role, message.content) for message in writer.messages] == [
        (MessageRole.ASSISTANT, "Agent 已完成。"),
        (MessageRole.USER, "请继续说明结果。"),
        (MessageRole.ASSISTANT, "后续普通回答。"),
    ]
    assert [(message.role, message.content) for message in llm.requests[0].history_messages] == [
        ("assistant", "Agent 已完成。")
    ]
    assert coordinator.tracked_conversation_count == 0


def test_cancelling_started_agent_turn_keeps_lease_until_worker_finishes() -> None:
    coordinator = ConversationTurnCoordinator()
    conversation_id = uuid4()
    _runtime, writer, _reader, _llm = _conversation_runtime(
        conversation_id=conversation_id,
        coordinator=coordinator,
        answer="不使用。",
    )
    worker = BlockingFactWorker(writer)
    executor = DialogueAgentTurnExecutor(
        coordinator=coordinator,
        worker_factory=BlockingFactWorkerFactory(worker),
    )

    async def scenario() -> None:
        started_turn = asyncio.create_task(executor.execute(_agent_turn_request(conversation_id)))
        assert await asyncio.to_thread(worker.started.wait, 1)

        started_turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await started_turn

        waiting_lease = asyncio.create_task(coordinator.acquire(conversation_id))
        await asyncio.sleep(0)
        assert not waiting_lease.done()

        worker.release.set()
        next_lease = await asyncio.wait_for(waiting_lease, timeout=1)
        next_lease.release()

    asyncio.run(scenario())

    assert worker.events == ["agent_result"]
    assert worker.closed is True
    assert coordinator.tracked_conversation_count == 0
