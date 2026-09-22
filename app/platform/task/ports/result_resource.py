from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TaskResultResource:
    """客户端可见的结果资源元数据，不携带内容或物理路径。"""

    resource_id: str
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.resource_id, str) or not self.resource_id.strip():
            raise ValueError("结果资源标识不能为空。")
        if not isinstance(self.file_name, str) or not self.file_name.strip():
            raise ValueError("结果资源文件名不能为空。")
        if not isinstance(self.media_type, str) or not self.media_type.strip():
            raise ValueError("结果资源媒体类型不能为空。")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes <= 0:
            raise ValueError("结果资源大小必须为正整数。")
        if not isinstance(self.sha256, str) or re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256) is None:
            raise ValueError("结果资源哈希无效。")


class TaskResultResourceReaderPort(Protocol):
    def list_resources(self, *, task_id: UUID, owner_subject: str, conversation_id: str) -> tuple[TaskResultResource, ...] | None: ...


__all__ = ["TaskResultResource", "TaskResultResourceReaderPort"]
