from __future__ import annotations

from threading import Event

from app.platform.task.application import ManagedWorkerStage, TaskWorkerRunner


def test_runner_completes_empty_poll_and_closes_each_stage() -> None:
    calls: list[str] = []

    def stage_factory() -> ManagedWorkerStage:
        return ManagedWorkerStage(
            name="tender",
            execute=lambda: calls.append("execute"),
            close=lambda: calls.append("close"),
        )

    TaskWorkerRunner(
        (stage_factory,),
        poll_interval_seconds=1,
    ).run_once()

    assert calls == ["execute", "close"]


def test_runner_isolates_stage_failure_and_reports_close_failure() -> None:
    calls: list[str] = []
    errors: list[str] = []

    def failed_stage() -> ManagedWorkerStage:
        return ManagedWorkerStage(
            name="recovery",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("failed")),
            close=lambda: calls.append("recovery-close"),
        )

    def healthy_stage() -> ManagedWorkerStage:
        return ManagedWorkerStage(
            name="tender",
            execute=lambda: calls.append("tender-execute"),
            close=lambda: (_ for _ in ()).throw(RuntimeError("close failed")),
        )

    TaskWorkerRunner(
        (failed_stage, healthy_stage),
        poll_interval_seconds=1,
        error_handler=errors.append,
    ).run_once()

    assert calls == ["recovery-close", "tender-execute"]
    assert errors == ["recovery", "tender"]


def test_runner_creates_new_stage_resources_for_each_poll() -> None:
    created: list[int] = []
    closed: list[int] = []

    def stage_factory() -> ManagedWorkerStage:
        resource_id = len(created) + 1
        created.append(resource_id)
        return ManagedWorkerStage(
            name=f"stage-{resource_id}",
            execute=lambda resource_id=resource_id: None,
            close=lambda resource_id=resource_id: closed.append(resource_id),
        )

    runner = TaskWorkerRunner((stage_factory,), poll_interval_seconds=1)
    runner.run_once()
    runner.run_once()

    assert created == [1, 2]
    assert closed == [1, 2]


def test_runner_stops_after_stage_requests_stop() -> None:
    stop_event = Event()
    executions = 0

    def stage_factory() -> ManagedWorkerStage:
        def execute() -> None:
            nonlocal executions
            executions += 1
            stop_event.set()

        return ManagedWorkerStage(name="tender", execute=execute, close=lambda: None)

    TaskWorkerRunner(
        (stage_factory,),
        poll_interval_seconds=60,
    ).run_forever(stop_event=stop_event)

    assert executions == 1
