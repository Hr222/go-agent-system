from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.modules.security.domain.principal import RequestPrincipal


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
