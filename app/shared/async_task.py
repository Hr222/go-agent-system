from __future__ import annotations

import asyncio
from typing import TypeVar

TaskResult = TypeVar("TaskResult")


async def await_shielded_task(task: asyncio.Task[TaskResult]) -> TaskResult:
    """等待受保护任务收口，即使调用方重复取消也不遗留后台任务。"""

    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
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
