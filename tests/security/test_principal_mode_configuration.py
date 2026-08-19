from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


def test_principal_mode_defaults_to_anonymous_without_a_static_subject() -> None:
    configuration = _settings()

    assert configuration.request_principal_mode == "anonymous"
    assert configuration.static_principal_subject == ""
    assert configuration.static_principal_permission_tuple == ()


def test_static_principal_configuration_normalizes_permissions() -> None:
    configuration = _settings(
        request_principal_mode="static",
        static_principal_subject=" local-operator ",
        static_principal_permissions="agent:tender:execute, agent:tender:execute, ,chat:write",
    )

    assert configuration.static_principal_subject == " local-operator "
    assert configuration.static_principal_permission_tuple == (
        "agent:tender:execute",
        "chat:write",
    )


def test_static_principal_mode_requires_a_subject() -> None:
    with pytest.raises(ValidationError, match="STATIC_PRINCIPAL_SUBJECT"):
        _settings(request_principal_mode="static")


def test_invalid_principal_mode_is_rejected() -> None:
    with pytest.raises(ValidationError, match="request_principal_mode"):
        _settings(request_principal_mode="token")
