from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TaskResultResource:
    """Task 结果资源的客户端安全元数据，不携带文件内容或物理路径。"""

    resource_id: str
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str


class TaskResultResourceReaderPort(Protocol):
    """读取已完成 Task 的资源清单；实现方负责附件生命周期校验。"""

    def list_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
    ) -> tuple[TaskResultResource, ...] | None: ...


__all__ = ["TaskResultResource", "TaskResultResourceReaderPort"]
