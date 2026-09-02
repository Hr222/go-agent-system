from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

TaskResult = TypeVar("TaskResult")


async def await_shielded_task(
    task: asyncio.Task[TaskResult],
    *,
    on_cancel: Callable[[], None] | None = None,
) -> TaskResult:
    """等待受保护任务收口，即使调用方重复取消也不遗留后台任务。"""

    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if on_cancel is not None:
            on_cancel()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        if task.done():
            try:
                task.result()
            except BaseException:
                pass
        raise


async def run_sync_protected(operation: Callable[[], TaskResult]) -> TaskResult:
    """在受保护的线程任务中运行不可取消的同步操作。"""

    task = asyncio.create_task(asyncio.to_thread(operation))
    return await await_shielded_task(task)
