from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.modules.attachment.contracts import (
    AttachmentAccessContext,
    AttachmentReadResult,
    AttachmentRef,
    AttachmentStatus,
)
from app.modules.attachment.ports.storage_port import AttachmentStoragePort
from app.shared.config import settings

_ATTACHMENT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_COPY_CHUNK_SIZE_BYTES = 1024 * 1024


@dataclass(slots=True)
class _AttachmentRecord:
    reference: AttachmentRef
    owner_subject: str | None
    conversation_id: str | None
    expires_at: datetime
    status: AttachmentStatus = "available"


class FilesystemAttachmentStorage(AttachmentStoragePort):
    """Store temporary attachments with server-side access and lifecycle state."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        max_size_bytes: int | None = None,
        retention_seconds: int | None = None,
        allowed_media_types: Iterable[str] | None = None,
    ) -> None:
        self.workspace_root = workspace_root.expanduser().resolve()
        self.attachment_root = (self.workspace_root / "attachments").resolve()
        self.storage_root = self.attachment_root
        self.attachment_root.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = (
            settings.attachment_max_size_bytes if max_size_bytes is None else max_size_bytes
        )
        self.retention_seconds = (
            settings.attachment_retention_seconds
            if retention_seconds is None
            else retention_seconds
        )
        configured_media_types = (
            settings.attachment_allowed_media_type_tuple
            if allowed_media_types is None
            else tuple(allowed_media_types)
        )
        self.allowed_media_types = frozenset(
            media_type.strip().lower()
            for media_type in configured_media_types
            if media_type.strip()
        )
        if self.max_size_bytes <= 0:
            raise ValueError("附件文件大小上限必须为正整数。")
        if self.retention_seconds <= 0:
            raise ValueError("附件暂存保留时间必须为正整数。")
        if not self.allowed_media_types:
            raise ValueError("附件媒体类型配置不能为空。")

        # This state is process-local until a shared metadata store becomes necessary.
        self._records: dict[str, _AttachmentRecord] = {}

    def stage_attachment(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
        context: AttachmentAccessContext,
    ) -> AttachmentRef:
        self.cleanup_expired()
        if not isinstance(context, AttachmentAccessContext):
            raise ValueError("附件访问上下文无效。")
        normalized_file_name = Path(file_name or "").name
        if (
            not normalized_file_name
            or normalized_file_name in {".", ".."}
            or normalized_file_name.startswith(".")
        ):
            raise ValueError("附件必须包含有效文件名。")
        normalized_media_type = (media_type or "").strip().lower()
        if normalized_media_type not in self.allowed_media_types:
            raise ValueError("附件媒体类型不受支持。")

        attachment_id = uuid4().hex
        target_dir = self.attachment_root / attachment_id
        target_dir.mkdir(parents=True, exist_ok=False)
        target_path = target_dir / normalized_file_name
        partial_path = target_dir / f".{attachment_id}.part"
        digest = hashlib.sha256()
        size_bytes = 0

        try:
            file_stream.seek(0)
            with partial_path.open("wb") as handle:
                while chunk := file_stream.read(_COPY_CHUNK_SIZE_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_size_bytes:
                        raise ValueError(f"附件不能超过 {self.max_size_bytes} 字节。")
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()

            if size_bytes <= 0:
                raise ValueError("附件不能为空。")
            partial_path.replace(target_path)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        reference = AttachmentRef(
            attachment_id=attachment_id,
            file_name=normalized_file_name,
            media_type=normalized_media_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )
        created_at = datetime.now(UTC)
        self._records[attachment_id] = _AttachmentRecord(
            reference=reference,
            owner_subject=context.subject,
            conversation_id=context.conversation_id,
            expires_at=created_at + timedelta(seconds=self.retention_seconds),
        )
        return reference

    def stage(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
        context: AttachmentAccessContext,
    ) -> AttachmentRef:
        """Short alias for callers that treat storage as a generic staging port."""

        return self.stage_attachment(
            file_name=file_name,
            media_type=media_type,
            file_stream=file_stream,
            context=context,
        )

    def store(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
        context: AttachmentAccessContext,
    ) -> AttachmentRef:
        """Compatibility alias for application adapters that call storage ``store``."""

        return self.stage_attachment(
            file_name=file_name,
            media_type=media_type,
            file_stream=file_stream,
            context=context,
        )

    def read(
        self,
        attachment: AttachmentRef | str,
        *,
        context: AttachmentAccessContext,
    ) -> AttachmentReadResult:
        self.cleanup_expired()
        attachment_id = self._attachment_id(attachment)
        if attachment_id is None:
            return self._missing_result()
        record = self._record_for_context(attachment_id, context)
        if record is None:
            return self._missing_result()
        if record.status != "available":
            return self._terminal_result(record)

        content = self._read_verified_content(record)
        if content is None:
            record.status = "missing"
            self._remove_attachment_dir(attachment_id)
            return self._terminal_result(record)
        return AttachmentReadResult(
            status="available",
            attachment=record.reference,
            content=content,
        )

    def consume(
        self,
        attachment_id: str,
        *,
        context: AttachmentAccessContext,
    ) -> AttachmentReadResult:
        self.cleanup_expired()
        normalized_id = self._attachment_id(attachment_id)
        if normalized_id is None:
            return self._missing_result()
        record = self._record_for_context(normalized_id, context)
        if record is None:
            return self._missing_result()
        if record.status != "available":
            return self._terminal_result(record)

        content = self._read_verified_content(record)
        if content is None:
            record.status = "missing"
            self._remove_attachment_dir(normalized_id)
            return self._terminal_result(record)

        record.status = "consumed"
        self._remove_attachment_dir(normalized_id)
        return AttachmentReadResult(
            status="available",
            attachment=record.reference,
            content=content,
        )

    def discard(self, attachment_id: str, *, context: AttachmentAccessContext) -> bool:
        self.cleanup_expired()
        normalized_id = self._attachment_id(attachment_id)
        if normalized_id is None:
            return False
        record = self._record_for_context(normalized_id, context)
        if record is None:
            return False
        self._remove_attachment_dir(normalized_id)
        del self._records[normalized_id]
        return True

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        reference_time = now or datetime.now(UTC)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        removed_count = 0

        for attachment_id, record in self._records.items():
            if record.status != "available" or record.expires_at > reference_time:
                continue
            record.status = "expired"
            if self._remove_attachment_dir(attachment_id):
                removed_count += 1

        expire_before = reference_time - timedelta(seconds=self.retention_seconds)
        for candidate in self.attachment_root.iterdir():
            if candidate.is_symlink() or not candidate.is_dir():
                continue
            if candidate.name in self._records:
                continue
            try:
                modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified_at >= expire_before:
                continue
            shutil.rmtree(candidate, ignore_errors=True)
            if not candidate.exists():
                removed_count += 1
        return removed_count

    def _record_for_context(
        self,
        attachment_id: str,
        context: AttachmentAccessContext,
    ) -> _AttachmentRecord | None:
        if not isinstance(context, AttachmentAccessContext):
            return None
        record = self._records.get(attachment_id)
        if record is None:
            return None
        if not record.owner_subject or context.subject != record.owner_subject:
            return None
        if record.conversation_id is not None and context.conversation_id != record.conversation_id:
            return None
        return record

    def _read_verified_content(self, record: _AttachmentRecord) -> bytes | None:
        try:
            target_dir = self._resolve_attachment_dir(record.reference.attachment_id)
        except ValueError:
            return None
        if not target_dir.exists() or not target_dir.is_dir():
            return None
        files = [
            path
            for path in target_dir.iterdir()
            if path.is_file() and not path.name.endswith(".part") and not path.name.startswith(".")
        ]
        if len(files) != 1:
            return None
        try:
            content = files[0].read_bytes()
        except OSError:
            return None
        content_hash = hashlib.sha256(content).hexdigest()
        if (
            len(content) != record.reference.size_bytes
            or content_hash != record.reference.sha256
        ):
            return None
        return content

    def _remove_attachment_dir(self, attachment_id: str) -> bool:
        try:
            target_dir = self._resolve_attachment_dir(attachment_id)
        except ValueError:
            return False
        existed = target_dir.exists()
        shutil.rmtree(target_dir, ignore_errors=True)
        return existed and not target_dir.exists()

    @staticmethod
    def _attachment_id(attachment: AttachmentRef | str) -> str | None:
        raw_id = attachment.attachment_id if isinstance(attachment, AttachmentRef) else attachment
        if not isinstance(raw_id, str):
            return None
        normalized_id = raw_id.strip()
        if not _ATTACHMENT_ID_PATTERN.fullmatch(normalized_id):
            return None
        return normalized_id

    @staticmethod
    def _missing_result() -> AttachmentReadResult:
        return AttachmentReadResult.unavailable(
            status="missing",
            error_code="ATTACHMENT_NOT_FOUND",
        )

    @staticmethod
    def _terminal_result(record: _AttachmentRecord) -> AttachmentReadResult:
        error_code = {
            "consumed": "ATTACHMENT_CONSUMED",
            "expired": "ATTACHMENT_EXPIRED",
            "missing": "ATTACHMENT_NOT_FOUND",
        }[record.status]
        return AttachmentReadResult.unavailable(
            status=record.status,
            error_code=error_code,
            attachment=replace(record.reference, status=record.status),
        )

    def _resolve_attachment_dir(self, attachment_id: str) -> Path:
        normalized_id = attachment_id.strip()
        if not _ATTACHMENT_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("attachment_id 格式无效。")
        target_dir = (self.attachment_root / normalized_id).resolve()
        try:
            target_dir.relative_to(self.attachment_root)
        except ValueError as exc:
            raise ValueError("attachment_id 不在附件暂存目录内。") from exc
        if target_dir.parent != self.attachment_root:
            raise ValueError("attachment_id 目录层级无效。")
        return target_dir


AttachmentStorageService = FilesystemAttachmentStorage

__all__ = ["AttachmentStorageService", "FilesystemAttachmentStorage"]
