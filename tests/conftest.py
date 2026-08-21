from __future__ import annotations

import pytest

from app.shared.config import settings


@pytest.fixture(autouse=True)
def isolate_request_principal_configuration(monkeypatch: pytest.MonkeyPatch):
    """Keep the test suite independent from a developer's local mock principal."""

    monkeypatch.setattr(settings, "request_principal_mode", "anonymous")
    monkeypatch.setattr(settings, "static_principal_subject", "")
    monkeypatch.setattr(settings, "static_principal_permissions", "")
