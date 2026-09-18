from __future__ import annotations

from pathlib import Path

import pytest

from app.shared.config import Settings


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


def test_database_url_override_does_not_require_postgres_password() -> None:
    configuration = _settings(
        database_url_override="postgresql+psycopg://example.invalid/go_agent_system",
        postgres_password=None,
    )

    assert (
        configuration.database_url
        == "postgresql+psycopg://example.invalid/go_agent_system"
    )


def test_database_url_requires_password_without_override() -> None:
    configuration = _settings(database_url_override="", postgres_password=None)

    with pytest.raises(ValueError, match="DATABASE_URL 或 POSTGRES_PASSWORD"):
        _ = configuration.database_url


def test_distributed_database_configuration_has_no_password_default() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    example_environment = (repository_root / ".env.example").read_text(encoding="utf-8")
    compose = (repository_root / "docker/postgres/docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "POSTGRES_PASSWORD=" in example_environment
    assert "POSTGRES_PASSWORD=123456" not in example_environment
    assert "POSTGRES_PASSWORD: \"${POSTGRES_PASSWORD:?" in compose
