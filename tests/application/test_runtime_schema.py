from __future__ import annotations

from app.composition import runtime


def test_inspect_task_schema_returns_tuple_and_setup_guide(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        runtime,
        "safe_find_missing_task_tables",
        lambda engine: ["task_event"],
    )

    result = runtime.inspect_task_schema()

    assert result.missing_tables == ("task_event",)
    assert "013_task_lifecycle.sql" in result.setup_guide


def test_inspect_task_schema_represents_database_unavailable(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(runtime, "safe_find_missing_task_tables", lambda engine: None)

    result = runtime.inspect_task_schema()

    assert result.missing_tables is None
