from __future__ import annotations

import pytest

from app.interfaces.http.security import get_request_principal
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
