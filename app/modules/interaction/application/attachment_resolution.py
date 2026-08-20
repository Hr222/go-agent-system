"""Resolve opaque attachment IDs before they enter capability execution."""

from __future__ import annotations

from app.modules.attachment.contracts import AttachmentAccessContext
from app.modules.attachment.ports.read_port import AttachmentReadPort
from app.modules.interaction.domain.attachment import (
    AttachmentFieldDeclaration,
    AttachmentResolutionResult,
    ResolvedAttachment,
    attachment_field_declarations,
    is_opaque_attachment_id,
)
from app.modules.interaction.domain.capability import PlatformCapability


class CapabilityAttachmentResolver:
    """Read and constrain catalog-declared attachments using trusted access context."""

    def __init__(self, attachment_reader: AttachmentReadPort) -> None:
        self._attachment_reader = attachment_reader

    def resolve(
        self,
        *,
        capability: PlatformCapability,
        inputs: dict[str, object],
        access_context: AttachmentAccessContext,
    ) -> AttachmentResolutionResult:
        resolved_inputs = dict(inputs)
        for declaration in attachment_field_declarations(capability.input_schema):
            if declaration.field_name not in inputs:
                continue
            attachment_ids = _attachment_ids(inputs[declaration.field_name], declaration)
            if attachment_ids is None:
                return _rejected("ATTACHMENT_INPUT_INVALID")

            attachments: list[ResolvedAttachment] = []
            for attachment_id in attachment_ids:
                try:
                    read_result = self._attachment_reader.read(
                        attachment_id,
                        context=access_context,
                    )
                except Exception:  # noqa: BLE001 - storage is an availability boundary
                    return _rejected("ATTACHMENT_RESOLUTION_UNAVAILABLE")
                if (
                    read_result.status != "available"
                    or read_result.attachment is None
                    or read_result.content is None
                ):
                    # Storage deliberately uses the same public result for missing,
                    # expired, consumed, and unauthorized attachment references.
                    return _rejected("ATTACHMENT_UNAVAILABLE")
                if (
                    read_result.attachment.media_type.lower() not in declaration.allowed_media_types
                    or read_result.attachment.size_bytes > declaration.max_size_bytes
                    or len(read_result.content) > declaration.max_size_bytes
                ):
                    return _rejected("ATTACHMENT_CONSTRAINT_VIOLATION")
                attachments.append(
                    ResolvedAttachment(
                        reference=read_result.attachment,
                        content=read_result.content,
                    )
                )

            resolved_inputs[declaration.field_name] = (
                attachments[0] if declaration.max_count == 1 else tuple(attachments)
            )
        return AttachmentResolutionResult(status="resolved", inputs=resolved_inputs)


def _attachment_ids(
    value: object,
    declaration: AttachmentFieldDeclaration,
) -> tuple[str, ...] | None:
    if declaration.max_count == 1:
        if not is_opaque_attachment_id(value):
            return None
        return (value,)
    if (
        not isinstance(value, list)
        or not value
        or len(value) > declaration.max_count
        or any(not is_opaque_attachment_id(item) for item in value)
    ):
        return None
    return tuple(value)


def _rejected(error_code: str) -> AttachmentResolutionResult:
    return AttachmentResolutionResult(
        status="rejected",
        inputs={},
        error_code=error_code,
    )


__all__ = ["CapabilityAttachmentResolver"]
