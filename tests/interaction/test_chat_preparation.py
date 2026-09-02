from __future__ import annotations

import asyncio
import threading

import pytest

from app.platform.interaction.application.chat_preparation import (
    ThreadedInteractionChatPreparation,
)
from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamCommand,
    InteractionStreamEvent,
    InteractionStreamPreparation,
)


class BlockingPreparationWorker:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.closed = False
        self.cancelled = False

    def prepare(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation:
        del command
        self.started.set()
        self.release.wait(timeout=1)
        return InteractionStreamPreparation(
            kind="single_event",
            event=InteractionStreamEvent("result", {"status": "ready"}),
        )

    def cancel_preparation(self, command, preparation) -> None:  # noqa: ANN001
        del command, preparation
        self.cancelled = True

    def close(self) -> None:
        self.closed = True


class BlockingPreparationWorkerFactory:
    def __init__(self, worker: BlockingPreparationWorker) -> None:
        self.worker = worker

    def create(self) -> BlockingPreparationWorker:
        return self.worker


def test_threaded_chat_preparation_keeps_event_loop_running_and_closes_worker() -> None:
    worker = BlockingPreparationWorker()
    preparation = ThreadedInteractionChatPreparation(
        BlockingPreparationWorkerFactory(worker)
    )
    command = InteractionChatStreamCommand(
        user_input="hello",
        principal=object(),  # type: ignore[arg-type]
        provided_inputs={},
    )

    async def scenario() -> tuple[InteractionStreamPreparation, int]:
        task = asyncio.create_task(preparation.prepare(command))
        assert await asyncio.to_thread(worker.started.wait, 1)
        worker.release.set()
        ticks = 0
        while not task.done():
            ticks += 1
            await asyncio.sleep(0)
        return await task, ticks

    result, ticks = asyncio.run(scenario())

    assert result.kind == "single_event"
    assert ticks > 0
    assert worker.closed is True


def test_threaded_chat_preparation_cancellation_is_finalized_before_reraising() -> None:
    worker = BlockingPreparationWorker()
    preparation = ThreadedInteractionChatPreparation(
        BlockingPreparationWorkerFactory(worker)
    )
    command = InteractionChatStreamCommand(
        user_input="hello",
        principal=object(),  # type: ignore[arg-type]
        provided_inputs={},
    )

    async def scenario() -> None:
        operation = asyncio.create_task(preparation.prepare(command))
        assert await asyncio.to_thread(worker.started.wait, 1)
        operation.cancel()
        await asyncio.sleep(0)
        worker.release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(scenario())

    assert worker.cancelled is True
    assert worker.closed is True
