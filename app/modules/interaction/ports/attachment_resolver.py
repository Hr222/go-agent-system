"""Port for turning capability attachment references into internal inputs."""

from __future__ import annotations

from typing import Protocol

from app.modules.attachment.contracts import AttachmentAccessContext
from app.modules.interaction.domain.attachment import AttachmentResolutionResult
from app.modules.interaction.domain.capability import PlatformCapability


class CapabilityAttachmentResolverPort(Protocol):
    """Resolve only catalog-declared attachment fields under trusted context."""

    def resolve(
        self,
        *,
        capability: PlatformCapability,
        inputs: dict[str, object],
        access_context: AttachmentAccessContext,
    ) -> AttachmentResolutionResult: ...


__all__ = ["CapabilityAttachmentResolverPort"]
