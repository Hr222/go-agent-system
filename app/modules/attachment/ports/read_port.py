from __future__ import annotations

from typing import Protocol

from app.modules.attachment.contracts import AttachmentReadResult, AttachmentRef


class AttachmentReadPort(Protocol):
    """Application-facing port for reading server-managed attachment content."""

    def read(self, attachment: AttachmentRef) -> AttachmentReadResult: ...


__all__ = ["AttachmentReadPort"]
