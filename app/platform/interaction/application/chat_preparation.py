from __future__ import annotations

import asyncio
from threading import Event

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
        cancellation = Event()
        cancellation_handled = Event()
        task = asyncio.create_task(
            asyncio.to_thread(self._run_sync, command, cancellation, cancellation_handled)
        )
        try:
            return await await_shielded_task(task, on_cancel=cancellation.set)
        except asyncio.CancelledError:
            if task.done() and not task.cancelled() and not cancellation_handled.is_set():
                try:
                    preparation = task.result()
                except BaseException:
                    pass
                else:
                    cleanup = asyncio.create_task(
                        asyncio.to_thread(self._cancel_sync, command, preparation)
                    )
                    try:
                        await await_shielded_task(cleanup)
                    except BaseException:
                        # Cancellation remains the public result; cleanup failures are
                        # consumed by the task and the worker transaction is rolled back.
                        pass
            raise

    def _run_sync(
        self,
        command: InteractionChatStreamCommand,
        cancellation: Event,
        cancellation_handled: Event,
    ) -> InteractionStreamPreparation:
        worker: InteractionChatPreparationWorkerPort | None = None
        preparation: InteractionStreamPreparation | None = None
        try:
            worker = self._worker_factory.create()
            preparation = worker.prepare(command)
            if cancellation.is_set():
                cancellation_handled.set()
                self._cancel_worker(worker, command, preparation)
            return preparation
        finally:
            if (
                worker is not None
                and preparation is not None
                and cancellation.is_set()
                and not cancellation_handled.is_set()
            ):
                cancellation_handled.set()
                self._cancel_worker(worker, command, preparation)
            if worker is not None:
                worker.close()

    def _cancel_sync(
        self,
        command: InteractionChatStreamCommand,
        preparation: InteractionStreamPreparation,
    ) -> None:
        worker = self._worker_factory.create()
        try:
            self._cancel_worker(worker, command, preparation)
        finally:
            worker.close()

    @staticmethod
    def _cancel_worker(
        worker: InteractionChatPreparationWorkerPort,
        command: InteractionChatStreamCommand,
        preparation: InteractionStreamPreparation,
    ) -> None:
        cancel = getattr(worker, "cancel_preparation", None)
        if cancel is not None:
            cancel(command, preparation)


__all__ = ["ThreadedInteractionChatPreparation"]
