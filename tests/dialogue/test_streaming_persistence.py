from __future__ import annotations

import asyncio
from threading import Event

import pytest

import app.composition.root as composition_root
from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.ports import ConversationRecentMessageWindow
from app.platform.dialogue.application import ThreadedStreamingConversationPersistence
from app.platform.security.domain.principal import RequestPrincipal


class BlockingWorker:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.closed = False

    def create_conversation(self, *, principal):  # noqa: ANN001
        del principal
        self.started.set()
        self.release.wait(timeout=2)
        return "created"

    def close(self) -> None:
        self.closed = True


class BlockingWorkerFactory:
    def __init__(self, worker: BlockingWorker) -> None:
        self.worker = worker
        self.created = 0

    def create(self) -> BlockingWorker:
        self.created += 1
        return self.worker


def test_blocking_persistence_operation_does_not_block_event_loop() -> None:
    worker = BlockingWorker()
    persistence = ThreadedStreamingConversationPersistence(BlockingWorkerFactory(worker))
    heartbeat = asyncio.Event()

    async def scenario() -> None:
        operation = asyncio.create_task(
            persistence.create_conversation(principal=object())  # type: ignore[arg-type]
        )
        assert await asyncio.to_thread(worker.started.wait, 1)
        asyncio.get_running_loop().call_soon(heartbeat.set)
        await asyncio.wait_for(heartbeat.wait(), timeout=0.2)
        worker.release.set()
        assert await operation == "created"

    asyncio.run(scenario())
    assert worker.closed is True


def test_cancelled_persistence_operation_waits_for_worker_cleanup() -> None:
    worker = BlockingWorker()
    persistence = ThreadedStreamingConversationPersistence(BlockingWorkerFactory(worker))

    async def scenario() -> None:
        operation = asyncio.create_task(
            persistence.create_conversation(principal=object())  # type: ignore[arg-type]
        )
        assert await asyncio.to_thread(worker.started.wait, 1)
        operation.cancel()
        worker.release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())
    assert worker.closed is True


def test_repeated_cancellation_still_waits_for_worker_cleanup() -> None:
    worker = BlockingWorker()
    persistence = ThreadedStreamingConversationPersistence(BlockingWorkerFactory(worker))

    async def scenario() -> None:
        operation = asyncio.create_task(
            persistence.create_conversation(principal=object())  # type: ignore[arg-type]
        )
        assert await asyncio.to_thread(worker.started.wait, 1)
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        await asyncio.sleep(0.01)
        assert operation.done() is False
        worker.release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())
    assert worker.closed is True


def test_repeated_cancellation_consumes_worker_failure_after_cleanup() -> None:
    class FailingWorker(BlockingWorker):
        def create_conversation(self, *, principal):  # noqa: ANN001
            del principal
            self.started.set()
            self.release.wait(timeout=2)
            raise RuntimeError("database write failed")

    worker = FailingWorker()
    persistence = ThreadedStreamingConversationPersistence(BlockingWorkerFactory(worker))

    async def scenario() -> None:
        operation = asyncio.create_task(
            persistence.create_conversation(principal=object())  # type: ignore[arg-type]
        )
        assert await asyncio.to_thread(worker.started.wait, 1)
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        worker.release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())
    assert worker.closed is True


class TrackingSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


class CompositionState:
    def __init__(self) -> None:
        self.conversation = Conversation(owner_subject="user-1")
        self.messages: list[Message] = []
        self.fail_append = False


def _patch_composition_services(monkeypatch, state: CompositionState) -> list[TrackingSession]:  # noqa: ANN001
    sessions: list[TrackingSession] = []

    def session_local() -> TrackingSession:
        session = TrackingSession()
        sessions.append(session)
        return session

    class Access:
        def __init__(self, session: TrackingSession) -> None:
            self.session = session

        def create(self, command):  # noqa: ANN001
            del command
            return state.conversation

        def resolve(self, query):  # noqa: ANN001
            del query
            return state.conversation

    class Writer:
        def __init__(self, session: TrackingSession) -> None:
            self.session = session

        def append_message(self, *, conversation_id, role, content):  # noqa: ANN001
            if state.fail_append:
                raise RuntimeError("write failed")
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                sequence=len(state.messages) + 1,
            )
            state.messages.append(message)
            return message

    class Reader:
        def __init__(self, session: TrackingSession) -> None:
            self.session = session

        def read_recent_messages(self, *, conversation_id, through_sequence, limit):  # noqa: ANN001
            return ConversationRecentMessageWindow(
                conversation_id=conversation_id,
                messages=tuple(
                    message
                    for message in state.messages
                    if message.sequence <= through_sequence
                )[-limit:],
            )

    monkeypatch.setattr(composition_root, "SessionLocal", session_local)
    monkeypatch.setattr(composition_root, "build_conversation_access_service", Access)
    monkeypatch.setattr(composition_root, "build_conversation_write_service", Writer)
    monkeypatch.setattr(
        composition_root,
        "build_conversation_recent_message_read_service",
        Reader,
    )
    return sessions


def test_composition_worker_uses_a_fresh_session_and_closes_each_short_operation(
    monkeypatch,
) -> None:  # noqa: ANN001
    state = CompositionState()
    sessions = _patch_composition_services(monkeypatch, state)
    persistence = ThreadedStreamingConversationPersistence(
        composition_root._SessionScopedStreamingConversationPersistenceWorkerFactory()
    )
    principal = RequestPrincipal(subject="user-1", authenticated=True)

    async def scenario() -> None:
        conversation = await persistence.create_conversation(principal=principal)
        await persistence.resolve_conversation(
            principal=principal,
            conversation_id=conversation.id,
        )
        user_message = await persistence.append_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="问题",
        )
        await persistence.read_recent_messages(
            conversation_id=conversation.id,
            through_sequence=user_message.sequence,
            limit=20,
        )

    asyncio.run(scenario())

    assert len(sessions) == 4
    assert len({id(session) for session in sessions}) == 4
    assert [(session.commits, session.rollbacks, session.closes) for session in sessions] == [
        (1, 0, 1),
        (1, 0, 1),
        (1, 0, 1),
        (1, 0, 1),
    ]


def test_composition_worker_rolls_back_before_closing_on_operation_failure(
    monkeypatch,
) -> None:  # noqa: ANN001
    state = CompositionState()
    state.fail_append = True
    sessions = _patch_composition_services(monkeypatch, state)
    persistence = ThreadedStreamingConversationPersistence(
        composition_root._SessionScopedStreamingConversationPersistenceWorkerFactory()
    )

    with pytest.raises(RuntimeError, match="write failed"):
        asyncio.run(
            persistence.append_message(
                conversation_id=state.conversation.id,
                role=MessageRole.USER,
                content="问题",
            )
        )

    assert [(session.commits, session.rollbacks, session.closes) for session in sessions] == [
        (0, 1, 1),
    ]


def test_composition_worker_rolls_back_before_closing_on_assistant_failure(
    monkeypatch,
) -> None:  # noqa: ANN001
    state = CompositionState()
    state.fail_append = True
    sessions = _patch_composition_services(monkeypatch, state)
    persistence = ThreadedStreamingConversationPersistence(
        composition_root._SessionScopedStreamingConversationPersistenceWorkerFactory()
    )

    with pytest.raises(RuntimeError, match="write failed"):
        asyncio.run(
            persistence.append_message(
                conversation_id=state.conversation.id,
                role=MessageRole.ASSISTANT,
                content="回答",
            )
        )

    assert [(session.commits, session.rollbacks, session.closes) for session in sessions] == [
        (0, 1, 1),
    ]


def test_composition_worker_factory_closes_session_when_adapter_setup_fails(
    monkeypatch,
) -> None:  # noqa: ANN001
    sessions: list[TrackingSession] = []

    def session_local() -> TrackingSession:
        session = TrackingSession()
        sessions.append(session)
        return session

    def fail_access(session: TrackingSession) -> object:
        del session
        raise RuntimeError("adapter setup failed")

    monkeypatch.setattr(composition_root, "SessionLocal", session_local)
    monkeypatch.setattr(composition_root, "build_conversation_access_service", fail_access)

    with pytest.raises(RuntimeError, match="adapter setup failed"):
        composition_root._SessionScopedStreamingConversationPersistenceWorkerFactory().create()

    assert [(session.commits, session.rollbacks, session.closes) for session in sessions] == [
        (0, 1, 1),
    ]
