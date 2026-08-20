from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.modules.attachment.contracts import AttachmentReadResult, AttachmentRef
from app.modules.attachment.ports.storage_port import AttachmentStoragePort
from app.shared.config import settings

_ATTACHMENT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_COPY_CHUNK_SIZE_BYTES = 1024 * 1024


class FilesystemAttachmentStorage(AttachmentStoragePort):
    """Store opaque attachment references in an isolated temporary directory."""

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

        self._expired_ids: set[str] = set()

    def stage_attachment(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
    ) -> AttachmentRef:
        self.cleanup_expired()
        normalized_file_name = Path(file_name or "").name
        if not normalized_file_name:
            raise ValueError("附件必须包含文件名。")
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

        return AttachmentRef(
            attachment_id=attachment_id,
            file_name=normalized_file_name,
            media_type=normalized_media_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )

    def stage(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
    ) -> AttachmentRef:
        """Short alias for callers that treat storage as a generic staging port."""

        return self.stage_attachment(
            file_name=file_name,
            media_type=media_type,
            file_stream=file_stream,
        )

    def store(
        self,
        *,
        file_name: str | None,
        media_type: str | None,
        file_stream: BinaryIO,
    ) -> AttachmentRef:
        """Compatibility alias for application adapters that call storage ``store``."""

        return self.stage_attachment(
            file_name=file_name,
            media_type=media_type,
            file_stream=file_stream,
        )

    def read(self, attachment: AttachmentRef) -> AttachmentReadResult:
        self.cleanup_expired()
        attachment_id = attachment.attachment_id.strip()
        if not _ATTACHMENT_ID_PATTERN.fullmatch(attachment_id):
            return AttachmentReadResult.unavailable(
                status="missing",
                error_code="ATTACHMENT_NOT_FOUND",
                attachment=attachment,
            )
        if attachment.status != "available":
            status = attachment.status
            error_code = {
                "consumed": "ATTACHMENT_CONSUMED",
                "expired": "ATTACHMENT_EXPIRED",
                "missing": "ATTACHMENT_NOT_FOUND",
            }[status]
            return AttachmentReadResult.unavailable(
                status=status,
                error_code=error_code,
                attachment=attachment,
            )
        if attachment_id in self._expired_ids:
            return AttachmentReadResult.unavailable(
                status="expired",
                error_code="ATTACHMENT_EXPIRED",
                attachment=attachment,
            )

        target_dir = self._resolve_attachment_dir(attachment_id)
        if not target_dir.exists() or not target_dir.is_dir():
            return AttachmentReadResult.unavailable(
                status="missing",
                error_code="ATTACHMENT_NOT_FOUND",
                attachment=attachment,
            )
        files = [
            path
            for path in target_dir.iterdir()
            if path.is_file() and not path.name.endswith(".part") and not path.name.startswith(".")
        ]
        if len(files) != 1:
            return AttachmentReadResult.unavailable(
                status="missing",
                error_code="ATTACHMENT_NOT_FOUND",
                attachment=attachment,
            )

        try:
            content = files[0].read_bytes()
        except OSError:
            return AttachmentReadResult.unavailable(
                status="missing",
                error_code="ATTACHMENT_NOT_FOUND",
                attachment=attachment,
            )
        content_hash = hashlib.sha256(content).hexdigest()
        if len(content) != attachment.size_bytes or content_hash != attachment.sha256:
            return AttachmentReadResult.unavailable(
                status="missing",
                error_code="ATTACHMENT_NOT_FOUND",
                attachment=attachment,
            )
        return AttachmentReadResult(status="available", attachment=attachment, content=content)

    def discard(self, attachment_id: str) -> None:
        try:
            target_dir = self._resolve_attachment_dir(attachment_id)
        except ValueError:
            return
        shutil.rmtree(target_dir, ignore_errors=True)

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        reference_time = now or datetime.now(UTC)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        expire_before = reference_time - timedelta(seconds=self.retention_seconds)
        removed_count = 0
        for candidate in self.attachment_root.iterdir():
            if candidate.is_symlink() or not candidate.is_dir():
                continue
            try:
                modified_at = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified_at >= expire_before:
                continue
            candidate_id = candidate.name
            if _ATTACHMENT_ID_PATTERN.fullmatch(candidate_id):
                self._expired_ids.add(candidate_id)
            shutil.rmtree(candidate, ignore_errors=True)
            if not candidate.exists():
                removed_count += 1
        return removed_count

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
