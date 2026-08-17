from __future__ import annotations

import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from app.modules.ingestion.ports.upload_port import StagedUpload, UploadStoragePort
from app.shared.config import settings

SUPPORTED_UPLOAD_EXTENSIONS = {
    ".doc",
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
}
UNSUPPORTED_UPLOAD_MESSAGE = "当前仅支持 .doc/.docx/.pdf 以及常见图片扫描件文件。"
_UPLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_COPY_CHUNK_SIZE_BYTES = 1024 * 1024


class PolicyUploadService(UploadStoragePort):
    """处理单文件预览 / 入库流程的上传暂存。"""

    def __init__(
        self,
        workspace_root: Path,
        *,
        max_size_bytes: int | None = None,
        retention_seconds: int | None = None,
    ) -> None:
        self.workspace_root = workspace_root.expanduser().resolve()
        self.upload_root = (self.workspace_root / "uploads").resolve()
        self.document_root = (self.workspace_root / "documents").resolve()
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.document_root.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = (
            settings.policy_upload_max_size_bytes
            if max_size_bytes is None
            else max_size_bytes
        )
        self.retention_seconds = (
            settings.policy_upload_retention_seconds
            if retention_seconds is None
            else retention_seconds
        )
        if self.max_size_bytes <= 0:
            raise ValueError("上传文件大小上限必须为正整数。")
        if self.retention_seconds <= 0:
            raise ValueError("上传暂存保留时间必须为正整数。")

    def stage_upload(self, *, file_name: str | None, file_stream: BinaryIO) -> StagedUpload:
        self.cleanup_expired()
        normalized_file_name = Path(file_name or "").name
        if not normalized_file_name:
            raise ValueError("上传文件必须包含文件名。")

        extension = Path(normalized_file_name).suffix.lower()
        if extension not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise ValueError(UNSUPPORTED_UPLOAD_MESSAGE)

        upload_id = uuid.uuid4().hex
        target_dir = self.upload_root / upload_id
        target_dir.mkdir(parents=True, exist_ok=False)
        target_path = target_dir / normalized_file_name
        partial_path = target_dir / f".{upload_id}.part"

        try:
            # 先写隐藏临时文件，完整校验后再原子改名，避免解析流程读到半个文件。
            file_stream.seek(0)
            size_bytes = 0
            with partial_path.open("wb") as handle:
                while chunk := file_stream.read(_COPY_CHUNK_SIZE_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_size_bytes:
                        raise ValueError(f"上传文件不能超过 {self.max_size_bytes} 字节。")
                    handle.write(chunk)

            if size_bytes <= 0:
                raise ValueError("上传文件不能为空。")
            partial_path.replace(target_path)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        return StagedUpload(
            upload_id=upload_id,
            file_name=normalized_file_name,
            stored_path=str(target_path),
            size_bytes=size_bytes,
        )

    def resolve_upload(self, upload_id: str) -> str:
        # 每次取文件前清理过期目录，避免暂存文件无限积累。
        self.cleanup_expired()
        target_dir = self._resolve_upload_dir(upload_id)

        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"upload_id 对应的上传文件不存在：{upload_id}")

        files = [
            path
            for path in target_dir.iterdir()
            if path.is_file() and not path.name.endswith(".part")
        ]
        if not files:
            raise FileNotFoundError(f"未找到 upload_id 对应的暂存文件：{upload_id}")
        if len(files) > 1:
            raise RuntimeError(f"upload_id 对应了多个暂存文件：{upload_id}")

        return str(files[0])

    def promote_upload(self, upload_id: str) -> str:
        """Move an accepted upload to durable storage before persisting its path."""
        source_path = Path(self.resolve_upload(upload_id))
        source_dir = self._resolve_upload_dir(upload_id)
        target_dir = self._resolve_document_dir(upload_id)
        target_dir.mkdir(parents=True, exist_ok=False)
        target_path = target_dir / source_path.name

        try:
            source_path.replace(target_path)
            source_dir.rmdir()
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        return str(target_path)

    def discard_upload(self, upload_id: str) -> None:
        """Remove a staged upload or a promoted file when ingestion fails."""
        try:
            upload_dir = self._resolve_upload_dir(upload_id)
            document_dir = self._resolve_document_dir(upload_id)
        except ValueError:
            return
        shutil.rmtree(upload_dir, ignore_errors=True)
        shutil.rmtree(document_dir, ignore_errors=True)

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        """清理超过保留时间的上传暂存目录。"""
        reference_time = now or datetime.now(UTC)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        expire_before = reference_time - timedelta(seconds=self.retention_seconds)
        removed_count = 0

        for candidate in self.upload_root.iterdir():
            if candidate.is_symlink() or not candidate.is_dir():
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

    def _resolve_upload_dir(self, upload_id: str) -> Path:
        return self._resolve_child_dir(self.upload_root, upload_id)

    def _resolve_document_dir(self, upload_id: str) -> Path:
        return self._resolve_child_dir(self.document_root, upload_id)

    @staticmethod
    def _resolve_child_dir(root: Path, upload_id: str) -> Path:
        # 先校验 ID 格式，再做真实路径归一化，形成两层目录越界防线。
        normalized_id = upload_id.strip()
        if not _UPLOAD_ID_PATTERN.fullmatch(normalized_id):
            raise ValueError("upload_id 格式无效。")

        target_dir = (root / normalized_id).resolve()
        try:
            target_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("upload_id 不在上传暂存目录内。") from exc
        if target_dir.parent != root:
            raise ValueError("upload_id 目录层级无效。")
        return target_dir
