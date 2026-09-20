"""Tender 内部 Task Worker 的独立运行入口。"""

from __future__ import annotations

import signal
from threading import Event

from app.composition.task_worker import build_tender_worker_runner
from app.shared.config import settings
from app.shared.logging import configure_logging


def main() -> None:
    configure_logging(settings.log_level)
    stop_event = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    build_tender_worker_runner().run_forever(stop_event=stop_event)


if __name__ == "__main__":
    main()
