from __future__ import annotations

from fastapi import Depends, Request

from app.modules.security import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    PrincipalResolverPort,
    RequestPrincipal,
)


def get_principal_resolver() -> PrincipalResolverPort:
    """HTTP adapter seam for replacing anonymous access with real authentication."""

    return AnonymousPrincipalResolver()


def get_request_principal(
    request: Request,
    resolver: PrincipalResolverPort = Depends(get_principal_resolver),
) -> RequestPrincipal:
    context = PrincipalResolutionContext(headers=dict(request.headers.items()))
    return resolver.resolve(context)
