from __future__ import annotations

from app.interfaces.http.security import get_request_principal
from app.modules.security import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    RequestPrincipal,
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
