"""Tender 异步 Task 所需的业务端口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.business.agents.tender.contracts import TenderGenerateSkeletonResult
from app.platform.attachment.contracts import AttachmentAccessContext
from app.platform.attachment.ports.storage_port import AttachmentStoragePort
from app.platform.interaction.domain.agent_call import StructuredAgentCall


@dataclass(frozen=True, slots=True)
class TenderTaskInput:
    """Worker 可消费的安全快照事实，不携带文档字节。"""

    attachment_id: str
    file_name: str
    media_type: str
    sha256: str
    user_focus: str | None = None
    conversation_id: str | None = None


class TenderTaskInputSnapshotPort(Protocol):
    """将已解析 Tender 输入转换为 AgentTaskBridge 快照事实。"""

    def snapshot(self, call: StructuredAgentCall, profile):  # noqa: ANN001
        """返回 AgentTaskInputSnapshot；具体类型由交互端口定义。"""
        ...


class TenderTaskInputReaderPort(Protocol):
    """按可信主体读取异步任务快照正文。"""

    def read(self, snapshot: TenderTaskInput, *, owner_subject: str) -> bytes: ...


class TenderTaskResultStorePort(Protocol):
    """只供内部 Executor 保存已验证 Tender 结果。"""

    def save(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        result: TenderGenerateSkeletonResult,
    ) -> str: ...


class AttachmentTenderTaskInputReader(TenderTaskInputReaderPort):
    """通过既有附件存储读取内容，并再次执行主体与会话绑定校验。"""

    def __init__(self, storage: AttachmentStoragePort) -> None:
        self._storage = storage

    def read(self, snapshot: TenderTaskInput, *, owner_subject: str) -> bytes:
        result = self._storage.read(
            snapshot.attachment_id,
            context=AttachmentAccessContext(
                subject=owner_subject,
                conversation_id=snapshot.conversation_id,
            ),
        )
        if result.status != "available" or result.attachment is None or result.content is None:
            raise ValueError("Tender 输入附件不可用。")
        if (
            result.attachment.file_name != snapshot.file_name
            or result.attachment.media_type != snapshot.media_type
            or result.attachment.sha256 != snapshot.sha256
        ):
            raise ValueError("Tender 输入附件校验失败。")
        return result.content


class InMemoryTenderTaskResultStore(TenderTaskResultStorePort):
    """测试和单进程验收替身；按 task_id 幂等保存。"""

    def __init__(self) -> None:
        self.results: dict[UUID, TenderGenerateSkeletonResult] = {}

    def save(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        result: TenderGenerateSkeletonResult,
    ) -> str:
        self.results.setdefault(task_id, result)
        return f"tender-result:{task_id}"


class FilesystemTenderTaskResultStore(TenderTaskResultStorePort):
    """将内部结果写入运行时目录，不提供公开读取接口。"""

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        result: TenderGenerateSkeletonResult,
    ) -> str:
        import base64
        import json

        target = self._root / f"{task_id}.json"
        if target.exists():
            return f"tender-result:{task_id}"
        payload = {
            "task_id": str(task_id),
            "owner_subject": owner_subject,
            "analysis": result.analysis.model_dump(mode="json"),
            "model": result.model,
            "prompt_version": result.prompt_version,
            "artifacts": [
                {
                    "file_name": artifact.file_name,
                    "media_type": artifact.media_type,
                    "content_base64": base64.b64encode(artifact.content).decode("ascii"),
                }
                for artifact in result.artifacts
            ],
        }
        temporary = target.with_suffix(".part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return f"tender-result:{task_id}"


__all__ = [
    "AttachmentTenderTaskInputReader",
    "FilesystemTenderTaskResultStore",
    "InMemoryTenderTaskResultStore",
    "TenderTaskInput",
    "TenderTaskInputReaderPort",
    "TenderTaskInputSnapshotPort",
    "TenderTaskResultStorePort",
]
