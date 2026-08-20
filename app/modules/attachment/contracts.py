from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

AttachmentStatus = Literal["available", "consumed", "expired", "missing"]
AttachmentErrorCode = Literal[
    "ATTACHMENT_CONSUMED",
    "ATTACHMENT_EXPIRED",
    "ATTACHMENT_NOT_FOUND",
]

_ATTACHMENT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    """Opaque, serializable metadata for a server-managed attachment."""

    attachment_id: str
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: AttachmentStatus = "available"

    @classmethod
    def issue(
        cls,
        *,
        file_name: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
    ) -> "AttachmentRef":
        """Issue a new server-generated opaque reference."""

        return cls(
            attachment_id=uuid4().hex,
            file_name=file_name,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    def __post_init__(self) -> None:
        if not _ATTACHMENT_ID_PATTERN.fullmatch(self.attachment_id):
            raise ValueError("attachment_id must be a generated opaque identifier")
        if not self.file_name.strip():
            raise ValueError("attachment file_name must be non-empty")
        if not self.media_type.strip():
            raise ValueError("attachment media_type must be non-empty")
        if self.size_bytes < 0:
            raise ValueError("attachment size_bytes must be non-negative")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256.lower()):
            raise ValueError("attachment sha256 must be a hexadecimal digest")

    def public_dict(self) -> dict[str, object]:
        """Return the complete client-safe reference without content or paths."""

        return {
            "attachment_id": self.attachment_id,
            "file_name": self.file_name,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class AttachmentReadResult:
    """Stable result boundary for attachment content reads."""

    status: AttachmentStatus
    attachment: AttachmentRef | None = None
    content: bytes | None = None
    error_code: AttachmentErrorCode | None = None

    def __post_init__(self) -> None:
        if self.status == "available":
            if self.attachment is None or self.content is None:
                raise ValueError("available attachment reads require metadata and content")
            if self.attachment.status != "available":
                raise ValueError("available reads require an available attachment reference")
            if not self.content:
                raise ValueError("available attachment reads require non-empty content")
            if self.error_code is not None:
                raise ValueError("available attachment reads cannot contain an error code")
            return

        if self.content is not None:
            raise ValueError("unavailable attachment reads must not contain content")
        if self.error_code is None:
            raise ValueError("unavailable attachment reads require an error code")

    @classmethod
    def unavailable(
        cls,
        *,
        status: Literal["consumed", "expired", "missing"],
        error_code: AttachmentErrorCode,
        attachment: AttachmentRef | None = None,
    ) -> "AttachmentReadResult":
        return cls(
            status=status,
            attachment=attachment,
            error_code=error_code,
        )


__all__ = [
    "AttachmentErrorCode",
    "AttachmentReadResult",
    "AttachmentRef",
    "AttachmentStatus",
]
