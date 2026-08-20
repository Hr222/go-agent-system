from __future__ import annotations

from datetime import datetime
from typing import BinaryIO, Protocol

from app.modules.attachment.contracts import AttachmentReadResult, AttachmentRef


class AttachmentStoragePort(Protocol):
    """Application-facing port for temporary attachment storage."""

    def stage_attachment(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
    ) -> AttachmentRef: ...

    def read(self, attachment: AttachmentRef) -> AttachmentReadResult: ...

    def discard(self, attachment_id: str) -> None: ...

    def cleanup_expired(self, *, now: datetime | None = None) -> int: ...


__all__ = ["AttachmentStoragePort"]
