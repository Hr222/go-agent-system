from __future__ import annotations

from fastapi import Depends, Request

from app.modules.security import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    PrincipalResolverPort,
    RequestPrincipal,
    StaticPrincipalResolver,
)
from app.shared.config import settings


def get_principal_resolver() -> PrincipalResolverPort:
    """Build the configured server-side principal resolver for an HTTP request."""

    if settings.request_principal_mode == "static":
        return StaticPrincipalResolver(
            subject=settings.static_principal_subject,
            permissions=settings.static_principal_permission_tuple,
        )

    return AnonymousPrincipalResolver()


def get_request_principal(
    request: Request,
    resolver: PrincipalResolverPort = Depends(get_principal_resolver),
) -> RequestPrincipal:
    context = PrincipalResolutionContext(headers=dict(request.headers.items()))
    return resolver.resolve(context)
