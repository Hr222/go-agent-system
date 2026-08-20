"""Capability-declared attachment inputs that remain inside server boundaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.modules.attachment.contracts import AttachmentRef

_ATTACHMENT_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class AttachmentDeclarationError(ValueError):
    """A capability attachment declaration is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class AttachmentFieldDeclaration:
    """The limits a capability applies to one client attachment-reference field."""

    field_name: str
    allowed_media_types: tuple[str, ...]
    max_size_bytes: int
    max_count: int


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    """Verified content for an adapter, never a client or LLM-facing value."""

    reference: AttachmentRef
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class AttachmentResolutionResult:
    """A resolver result whose successful inputs are server-internal only."""

    status: Literal["resolved", "rejected"]
    inputs: dict[str, object]
    error_code: str | None = None


def attachment_field_declarations(
    input_schema: Mapping[str, object],
) -> tuple[AttachmentFieldDeclaration, ...]:
    """Read and validate ``x-attachment`` declarations from input properties.

    A scalar declaration uses a JSON Schema string property. A multi-value
    declaration uses an array with string items. This keeps public input as
    opaque IDs while allowing the resolver to replace it with internal values.
    """

    properties = input_schema.get("properties")
    if not isinstance(properties, Mapping):
        return ()

    declarations: list[AttachmentFieldDeclaration] = []
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(field_schema, Mapping):
            continue
        extension = field_schema.get("x-attachment")
        if extension is None:
            continue
        if not isinstance(extension, Mapping):
            raise AttachmentDeclarationError(f"{field_name}.x-attachment 必须是对象。")

        media_types = extension.get("allowed_media_types")
        if not isinstance(media_types, list) or not media_types:
            raise AttachmentDeclarationError(
                f"{field_name}.x-attachment.allowed_media_types 必须是非空列表。"
            )
        normalized_media_types = tuple(
            media_type.strip().lower()
            for media_type in media_types
            if isinstance(media_type, str) and media_type.strip()
        )
        if len(normalized_media_types) != len(media_types) or len(
            set(normalized_media_types)
        ) != len(normalized_media_types):
            raise AttachmentDeclarationError(
                f"{field_name}.x-attachment.allowed_media_types 必须是唯一的非空媒体类型。"
            )

        max_size_bytes = extension.get("max_size_bytes")
        max_count = extension.get("max_count")
        if not _is_positive_integer(max_size_bytes):
            raise AttachmentDeclarationError(
                f"{field_name}.x-attachment.max_size_bytes 必须是正整数。"
            )
        if not _is_positive_integer(max_count):
            raise AttachmentDeclarationError(f"{field_name}.x-attachment.max_count 必须是正整数。")

        if max_count == 1:
            if field_schema.get("type") != "string":
                raise AttachmentDeclarationError(f"单附件字段 {field_name} 必须声明为 string。")
        else:
            items = field_schema.get("items")
            if (
                field_schema.get("type") != "array"
                or not isinstance(items, Mapping)
                or items.get("type") != "string"
            ):
                raise AttachmentDeclarationError(
                    f"多附件字段 {field_name} 必须声明为 string items 的 array。"
                )

        declarations.append(
            AttachmentFieldDeclaration(
                field_name=field_name,
                allowed_media_types=normalized_media_types,
                max_size_bytes=max_size_bytes,
                max_count=max_count,
            )
        )
    return tuple(declarations)


def is_opaque_attachment_id(value: object) -> bool:
    return isinstance(value, str) and _ATTACHMENT_ID_PATTERN.fullmatch(value) is not None


def is_resolved_attachment_value(value: object, field_schema: object) -> bool:
    """Allow resolver output only for an explicitly declared attachment field."""

    if not isinstance(field_schema, Mapping) or "x-attachment" not in field_schema:
        return False
    if field_schema.get("type") == "string":
        return isinstance(value, ResolvedAttachment)
    return (
        field_schema.get("type") == "array"
        and isinstance(value, tuple)
        and bool(value)
        and all(isinstance(item, ResolvedAttachment) for item in value)
    )


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


__all__ = [
    "AttachmentDeclarationError",
    "AttachmentFieldDeclaration",
    "AttachmentResolutionResult",
    "ResolvedAttachment",
    "attachment_field_declarations",
    "is_opaque_attachment_id",
    "is_resolved_attachment_value",
]
