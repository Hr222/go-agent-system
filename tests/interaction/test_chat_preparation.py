from __future__ import annotations

import asyncio
import threading
import time

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
        self.closed = False

    def prepare(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation:
        del command
        self.started.set()
        time.sleep(0.05)
        return InteractionStreamPreparation(
            kind="single_event",
            event=InteractionStreamEvent("result", {"status": "ready"}),
        )

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
        ticks = 0
        while not task.done():
            ticks += 1
            await asyncio.sleep(0)
        return await task, ticks

    result, ticks = asyncio.run(scenario())

    assert result.kind == "single_event"
    assert ticks > 0
    assert worker.closed is True
