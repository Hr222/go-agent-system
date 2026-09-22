from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.persistence import schema_health


class FakeInspector:
    def __init__(self, tables: set[str]) -> None:
        self.tables = tables

    def has_table(self, table: str) -> bool:
        return table in self.tables


def test_find_missing_task_tables_reports_all_missing_tables(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        schema_health,
        "inspect",
        lambda engine: FakeInspector({"task", "task_event"}),
    )

    assert schema_health.find_missing_task_tables(object()) == [
        "task_attempt",
        "task_command_receipt",
    ]


def test_safe_find_missing_task_tables_returns_empty_when_schema_is_complete(
    monkeypatch,
) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        schema_health,
        "inspect",
        lambda engine: FakeInspector(set(schema_health.REQUIRED_TASK_TABLES)),
    )

    assert schema_health.safe_find_missing_task_tables(object()) == []


def test_safe_find_missing_task_tables_hides_database_errors(monkeypatch) -> None:  # noqa: ANN001
    def fail(engine):  # noqa: ANN001
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(schema_health, "inspect", fail)

    assert schema_health.safe_find_missing_task_tables(object()) is None
