from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.interfaces.http.security import get_principal_resolver, get_request_principal
from app.modules.security import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    RequestPrincipal,
    StaticPrincipalResolver,
)


def test_anonymous_resolver_returns_empty_permissions() -> None:
    principal = AnonymousPrincipalResolver().resolve(
        PrincipalResolutionContext(headers={"x-permissions": "agent:tender:execute"})
    )

    assert principal == RequestPrincipal.anonymous()
    assert principal.permission_tuple() == ()
    assert principal.authenticated is False


def test_request_principal_normalizes_permission_order_for_application_input() -> None:
    principal = RequestPrincipal(
        subject="internal-user",
        permissions=frozenset({"z:last", "a:first"}),
        authenticated=True,
    )

    assert principal.permission_tuple() == ("a:first", "z:last")
    assert principal.has_permission("a:first")
    assert not principal.has_permission("missing")


def test_static_resolver_returns_the_server_configured_principal() -> None:
    resolver = StaticPrincipalResolver(
        subject=" local-operator ",
        permissions=("agent:tender:execute", " agent:tender:execute ", ""),
    )

    first = resolver.resolve(PrincipalResolutionContext())
    second = resolver.resolve(
        PrincipalResolutionContext(headers={"x-permissions": "agent:other:execute"})
    )

    assert first == RequestPrincipal(
        subject="local-operator",
        permissions=frozenset({"agent:tender:execute"}),
        authenticated=True,
    )
    assert second == first


@pytest.mark.parametrize("subject", ("", "   ", None, 1))
def test_static_resolver_rejects_an_empty_or_non_text_subject(subject: object) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        StaticPrincipalResolver(subject=subject)  # type: ignore[arg-type]


def test_static_resolver_rejects_non_text_permissions() -> None:
    with pytest.raises(ValueError, match="permissions must be strings"):
        StaticPrincipalResolver(
            subject="local-operator",
            permissions=("agent:run", 1),  # type: ignore[arg-type]
        )


def test_http_security_adapter_can_be_replaced_without_changing_application_contract() -> None:
    class StaticResolver:
        def resolve(self, context: PrincipalResolutionContext) -> RequestPrincipal:
            assert "authorization" in context.headers
            return RequestPrincipal(
                subject="internal-user",
                permissions=frozenset({"agent:tender:execute"}),
                authenticated=True,
            )

    principal = get_request_principal(
        request=type(
            "RequestStub",
            (),
            {"headers": {"authorization": "test-token"}},
        )(),
        resolver=StaticResolver(),
    )

    assert principal.has_permission("agent:tender:execute")


def test_http_security_adapter_uses_anonymous_mode_by_default() -> None:
    resolver = get_principal_resolver()

    principal = resolver.resolve(
        PrincipalResolutionContext(headers={"x-permissions": "agent:tender:execute"})
    )

    assert isinstance(resolver, AnonymousPrincipalResolver)
    assert principal == RequestPrincipal.anonymous()


def test_http_security_adapter_uses_static_mode_from_server_configuration(
    monkeypatch,
) -> None:  # noqa: ANN001
    from app.shared.config import settings

    monkeypatch.setattr(settings, "request_principal_mode", "static")
    monkeypatch.setattr(settings, "static_principal_subject", "local-operator")
    monkeypatch.setattr(settings, "static_principal_permissions", "agent:tender:execute")

    resolver = get_principal_resolver()
    principal = resolver.resolve(
        PrincipalResolutionContext(headers={"x-permissions": "agent:other:execute"})
    )

    assert principal.subject == "local-operator"
    assert principal.permission_tuple() == ("agent:tender:execute",)
    assert principal.authenticated is True


def test_http_static_mode_never_uses_client_permission_header(monkeypatch) -> None:  # noqa: ANN001
    from app.shared.config import settings

    monkeypatch.setattr(settings, "request_principal_mode", "static")
    monkeypatch.setattr(settings, "static_principal_subject", "local-operator")
    monkeypatch.setattr(settings, "static_principal_permissions", "agent:tender:execute")

    principal = get_request_principal(
        request=type(
            "RequestStub",
            (),
            {"headers": {"x-permissions": "agent:admin:execute"}},
        )(),
        resolver=get_principal_resolver(),
    )

    assert principal.permission_tuple() == ("agent:tender:execute",)
    assert not principal.has_permission("agent:admin:execute")


def test_fastapi_injects_the_configured_static_principal(monkeypatch) -> None:  # noqa: ANN001
    from app.shared.config import settings

    monkeypatch.setattr(settings, "request_principal_mode", "static")
    monkeypatch.setattr(settings, "static_principal_subject", "local-operator")
    monkeypatch.setattr(settings, "static_principal_permissions", "agent:tender:execute")
    application = FastAPI()

    @application.get("/principal")
    def read_principal(
        principal: RequestPrincipal = Depends(get_request_principal),
    ) -> dict[str, object]:
        return {
            "subject": principal.subject,
            "permissions": principal.permission_tuple(),
            "authenticated": principal.authenticated,
        }

    response = TestClient(application).get(
        "/principal",
        headers={"x-permissions": "agent:admin:execute"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "subject": "local-operator",
        "permissions": ["agent:tender:execute"],
        "authenticated": True,
    }
