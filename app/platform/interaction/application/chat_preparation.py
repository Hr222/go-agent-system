from __future__ import annotations

import asyncio

from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamCommand,
    InteractionStreamPreparation,
)
from app.platform.interaction.ports.chat_preparation import (
    InteractionChatPreparationPort,
    InteractionChatPreparationWorkerFactoryPort,
    InteractionChatPreparationWorkerPort,
)
from app.shared.async_task import await_shielded_task


class ThreadedInteractionChatPreparation(InteractionChatPreparationPort):
    """把同步 Gateway 准备隔离到每次请求独立的短 Worker。"""

    def __init__(self, worker_factory: InteractionChatPreparationWorkerFactoryPort) -> None:
        self._worker_factory = worker_factory

    async def prepare(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation:
        task = asyncio.create_task(asyncio.to_thread(self._run_sync, command))
        return await await_shielded_task(task)

    def _run_sync(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation:
        worker: InteractionChatPreparationWorkerPort | None = None
        try:
            worker = self._worker_factory.create()
            return worker.prepare(command)
        finally:
            if worker is not None:
                worker.close()


__all__ = ["ThreadedInteractionChatPreparation"]
