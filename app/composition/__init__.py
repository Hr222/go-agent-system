"""Composition Root。"""

from app.composition.root import (
    ApplicationContainer,
    get_db_session,
    tender_mcp_dispatch_scope,
)

__all__ = ["ApplicationContainer", "get_db_session", "tender_mcp_dispatch_scope"]
