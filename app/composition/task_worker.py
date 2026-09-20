"""Tender Task Worker 的 Composition Root 组装。"""

from __future__ import annotations

from collections.abc import Callable

from app.composition.root import ApplicationContainer
from app.composition.task import (
    build_task_recovery_coordinator,
    build_task_retry_scheduler,
    build_tender_task_worker,
)
from app.infrastructure.persistence.session import SessionLocal
from app.platform.task.application import ManagedWorkerStage, TaskWorkerRunner
from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger("app.run_tender_task_worker")


def _session_stage(
    name: str,
    action_factory: Callable[[object], Callable[[], object]],
) -> ManagedWorkerStage:
    session = SessionLocal()
    try:
        action = action_factory(session)
    except Exception:
        session.close()
        raise
    return ManagedWorkerStage(name=name, execute=action, close=session.close)


def build_tender_worker_runner() -> TaskWorkerRunner:
    """固定组装 Tender 恢复、重试和执行阶段，不接受运行时执行器选择。"""

    def recovery(session: object) -> Callable[[], object]:
        return build_task_recovery_coordinator(
            session,  # type: ignore[arg-type]
            batch_size=settings.task_worker_batch_size,
        ).run_once

    def retry(session: object) -> Callable[[], object]:
        return build_task_retry_scheduler(
            session,  # type: ignore[arg-type]
            batch_size=settings.task_worker_batch_size,
        ).run_once

    def tender(session: object) -> ManagedWorkerStage:
        container = ApplicationContainer(session)  # type: ignore[arg-type]
        try:
            worker = build_tender_task_worker(
                session,  # type: ignore[arg-type]
                worker_id=settings.task_worker_id,
                tender_application=container.tender_application(),
                attachment_storage=container.attachment_storage(),
            )
        except Exception:
            container.close()
            raise

        def close() -> None:
            try:
                container.close()
            finally:
                session.close()  # type: ignore[union-attr]

        # TenderApplication may own provider clients, so it closes before Session.
        return ManagedWorkerStage(name="tender", execute=worker.poll_once, close=close)

    def stage(name: str, factory: Callable[[object], Callable[[], object]]) -> ManagedWorkerStage:
        return _session_stage(name, factory)

    def tender_stage() -> ManagedWorkerStage:
        session = SessionLocal()
        try:
            return tender(session)
        except Exception:
            session.close()
            raise

    return TaskWorkerRunner(
        stage_factories=(
            lambda: stage("recovery", recovery),
            lambda: stage("retry", retry),
            tender_stage,
        ),
        poll_interval_seconds=settings.task_worker_poll_interval_seconds,
        error_handler=lambda stage_name: logger.error("Task Worker 阶段失败 stage=%s", stage_name),
    )


__all__ = ["build_tender_worker_runner"]
