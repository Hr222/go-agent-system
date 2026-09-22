from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main


def _run_with_task_status(monkeypatch, status, caplog) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        main,
        "inspect_knowledge_base_schema",
        lambda: SimpleNamespace(missing_tables=()),
    )
    monkeypatch.setattr(main, "inspect_task_schema", lambda: status)

    with TestClient(main.create_app()):
        pass


def test_startup_logs_task_schema_ready(monkeypatch, caplog) -> None:  # noqa: ANN001
    with caplog.at_level("INFO", logger="app.main"):
        _run_with_task_status(
            monkeypatch,
            SimpleNamespace(missing_tables=(), setup_guide="guide"),
            caplog,
        )

    assert "Task 表结构检查通过" in caplog.text


def test_startup_logs_missing_task_tables_and_guide(monkeypatch, caplog) -> None:  # noqa: ANN001
    with caplog.at_level("WARNING", logger="app.main"):
        _run_with_task_status(
            monkeypatch,
            SimpleNamespace(missing_tables=("task",), setup_guide="run migration"),
            caplog,
        )

    assert "Task 表结构未就绪" in caplog.text
    assert "run migration" in caplog.text


def test_startup_logs_task_database_unavailable(monkeypatch, caplog) -> None:  # noqa: ANN001
    with caplog.at_level("WARNING", logger="app.main"):
        _run_with_task_status(
            monkeypatch,
            SimpleNamespace(missing_tables=None, setup_guide="guide"),
            caplog,
        )

    assert "已跳过 Task 表结构检查" in caplog.text
