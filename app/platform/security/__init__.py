"""Security boundary contracts used by external adapters and application services."""

from app.platform.security.domain.principal import RequestPrincipal
from app.platform.security.ports.principal_resolver import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    PrincipalResolverPort,
    StaticPrincipalResolver,
)

__all__ = [
    "AnonymousPrincipalResolver",
    "PrincipalResolutionContext",
    "PrincipalResolverPort",
    "RequestPrincipal",
    "StaticPrincipalResolver",
]
