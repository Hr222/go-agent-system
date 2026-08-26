from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.platform.security.domain.principal import RequestPrincipal


@dataclass(frozen=True, slots=True)
class PrincipalResolutionContext:
    """Protocol-neutral request facts available to a future auth adapter."""

    headers: Mapping[str, str] = field(default_factory=dict)


class PrincipalResolverPort(Protocol):
    """Resolve trusted identity facts without coupling applications to an auth protocol."""

    def resolve(self, context: PrincipalResolutionContext) -> RequestPrincipal: ...


class AnonymousPrincipalResolver:
    """Default resolver while user management and authentication are not implemented."""

    def resolve(self, context: PrincipalResolutionContext) -> RequestPrincipal:
        del context
        return RequestPrincipal.anonymous()


class StaticPrincipalResolver:
    """Resolve one server-configured principal for local and controlled deployments."""

    def __init__(self, *, subject: str, permissions: Iterable[str] = ()) -> None:
        normalized_subject = subject.strip() if isinstance(subject, str) else ""
        if not normalized_subject:
            raise ValueError("Static principal subject must be a non-empty string")

        normalized_permissions: set[str] = set()
        for permission in permissions:
            if not isinstance(permission, str):
                raise ValueError("Static principal permissions must be strings")
            normalized_permission = permission.strip()
            if normalized_permission:
                normalized_permissions.add(normalized_permission)

        self._principal = RequestPrincipal(
            subject=normalized_subject,
            permissions=frozenset(normalized_permissions),
            authenticated=True,
        )

    def resolve(self, context: PrincipalResolutionContext) -> RequestPrincipal:
        del context
        return self._principal
