"""附件模块的 Composition Root。"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage


def build_attachment_storage(workspace_root: Path) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(workspace_root)
