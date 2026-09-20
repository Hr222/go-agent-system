"""受信任 Task Worker 的独立轮询运行边界。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from threading import Event
from time import sleep


@dataclass(frozen=True, slots=True)
class ManagedWorkerStage:
    """一次轮询阶段及其独立资源释放操作。"""

    name: str
    execute: Callable[[], object]
    close: Callable[[], None]


StageFactory = Callable[[], ManagedWorkerStage]
ErrorHandler = Callable[[str], None]


class TaskWorkerRunner:
    """按固定阶段轮询 Task，并隔离每个阶段的持久化资源。"""

    def __init__(
        self,
        stage_factories: Sequence[StageFactory],
        *,
        poll_interval_seconds: float,
        sleep_fn: Callable[[float], None] = sleep,
        error_handler: ErrorHandler | None = None,
    ) -> None:
        if not stage_factories:
            raise ValueError("Worker 至少需要一个轮询阶段。")
        if poll_interval_seconds <= 0:
            raise ValueError("Worker 轮询间隔必须为正数。")
        self._stage_factories = tuple(stage_factories)
        self._poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep_fn
        self._error_handler = error_handler or (lambda _stage_name: None)

    def run_once(self) -> None:
        """执行一轮恢复、重试和固定执行器阶段；单阶段失败不阻塞后续阶段。"""
        for stage_factory in self._stage_factories:
            stage: ManagedWorkerStage | None = None
            stage_name = "unknown"
            try:
                stage = stage_factory()
                stage_name = stage.name
                stage.execute()
            except Exception:  # noqa: BLE001 - 轮询边界只暴露稳定阶段错误
                self._error_handler(stage_name)
            finally:
                if stage is not None:
                    try:
                        stage.close()
                    except Exception:  # noqa: BLE001 - 资源释放不能阻塞后续阶段
                        self._error_handler(stage_name)

    def run_forever(self, *, stop_event: Event) -> None:
        """持续轮询，使用可中断等待避免停止信号额外阻塞一个完整周期。"""
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(self._poll_interval_seconds)


__all__ = ["ManagedWorkerStage", "TaskWorkerRunner"]
