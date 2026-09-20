"""Tender 异步 Task 所需的业务端口。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.business.agents.tender.contracts import TenderGenerateSkeletonResult
from app.platform.attachment.contracts import AttachmentAccessContext, AttachmentRef
from app.platform.attachment.ports.storage_port import AttachmentStoragePort
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.task.ports import (
    TaskResultResource,
    TaskResultResourceReaderPort,
)


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
        conversation_id: str | None = None,
    ) -> str: ...


class TenderTaskResourceStorePort(TaskResultResourceReaderPort, Protocol):
    """Tender 结果资源的受信任保存端口。"""

    def save_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
        result: TenderGenerateSkeletonResult,
    ) -> tuple[TaskResultResource, ...]: ...


class TenderResultResourceStoreError(ValueError):
    """结果资源无法完整保存或恢复。"""


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
        self.resources: dict[UUID, tuple[TaskResultResource, ...]] = {}
        self._resource_contexts: dict[UUID, tuple[str, str]] = {}

    def save(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        result: TenderGenerateSkeletonResult,
        conversation_id: str | None = None,
    ) -> str:
        del owner_subject, conversation_id
        self.results.setdefault(task_id, result)
        return f"tender-result:{task_id}"

    def save_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
        result: TenderGenerateSkeletonResult,
    ) -> tuple[TaskResultResource, ...]:
        existing = self.resources.get(task_id)
        if existing is not None:
            if self._resource_contexts.get(task_id) != (owner_subject, conversation_id):
                raise TenderResultResourceStoreError("Tender 结果资源归属不一致。")
            return existing
        resources = tuple(
            TaskResultResource(
                resource_id=f"memory:{task_id}:{index}",
                file_name=artifact.file_name,
                media_type=artifact.media_type,
                size_bytes=len(artifact.content),
                sha256=hashlib.sha256(artifact.content).hexdigest(),
            )
            for index, artifact in enumerate(result.artifacts)
            if artifact.content
        )
        self.resources[task_id] = resources
        self._resource_contexts[task_id] = (owner_subject, conversation_id)
        return resources

    def list_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
    ) -> tuple[TaskResultResource, ...] | None:
        if self._resource_contexts.get(task_id) != (owner_subject, conversation_id):
            return None
        return self.resources.get(task_id)


class FilesystemTenderTaskResultStore(TenderTaskResultStorePort):
    """保存内部结果，并把可交付文件映射为主体绑定的附件资源。"""

    def __init__(
        self,
        workspace_root: Path,
        *,
        attachment_storage: AttachmentStoragePort | None = None,
    ) -> None:
        self._root = workspace_root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._resource_root = self._root / "resources"
        self._resource_root.mkdir(parents=True, exist_ok=True)
        self._attachment_storage = attachment_storage

    def save(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        result: TenderGenerateSkeletonResult,
        conversation_id: str | None = None,
    ) -> str:
        import base64
        import json

        target = self._root / f"{task_id}.json"
        resources: tuple[TaskResultResource, ...] | None = None
        if self._attachment_storage is not None and conversation_id:
            resources = self.save_resources(
                task_id=task_id,
                owner_subject=owner_subject,
                conversation_id=conversation_id,
                result=result,
            )
        if target.exists():
            return f"tender-result:{task_id}"
        payload = {
            "task_id": str(task_id),
            "owner_subject": owner_subject,
            "analysis": result.analysis.model_dump(mode="json"),
            "model": result.model,
            "prompt_version": result.prompt_version,
        }
        if resources is not None:
            # 已资源化的结果不再在内部回执重复保存文件字节。
            payload["resources"] = [self._resource_payload(item) for item in resources]
        else:
            payload["artifacts"] = [
                {
                    "file_name": artifact.file_name,
                    "media_type": artifact.media_type,
                    "content_base64": base64.b64encode(artifact.content).decode("ascii"),
                }
                for artifact in result.artifacts
            ]
        temporary = target.with_suffix(".part")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
        except Exception:
            if self._attachment_storage is not None and conversation_id:
                self._discard_resources(task_id, owner_subject, conversation_id)
            raise
        return f"tender-result:{task_id}"

    def save_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
        result: TenderGenerateSkeletonResult,
    ) -> tuple[TaskResultResource, ...]:
        import io
        import json

        if self._attachment_storage is None:
            raise TenderResultResourceStoreError("Tender 结果资源依赖未配置。")
        if not conversation_id.strip():
            raise TenderResultResourceStoreError("Tender 结果缺少 Conversation 绑定。")
        manifest = self._resource_manifest_path(task_id)
        if manifest.exists():
            data = self._read_resource_data(manifest)
            if (
                data is not None
                and data.get("owner_subject") == owner_subject
                and data.get("conversation_id") == conversation_id
            ):
                resources = self.list_resources(
                    task_id=task_id,
                    owner_subject=owner_subject,
                    conversation_id=conversation_id,
                )
                if resources is not None:
                    return resources
                self._discard_resources(task_id, owner_subject, conversation_id)
            raise TenderResultResourceStoreError("Tender 结果资源清单无效。")
        if not result.artifacts or any(not artifact.content for artifact in result.artifacts):
            raise TenderResultResourceStoreError("Tender 结果缺少可交付文件。")

        created: list[TaskResultResource] = []
        try:
            for artifact in result.artifacts:
                reference = self._attachment_storage.stage_attachment(
                    file_name=artifact.file_name,
                    media_type=artifact.media_type,
                    file_stream=io.BytesIO(artifact.content),
                    context=AttachmentAccessContext(
                        subject=owner_subject,
                        conversation_id=conversation_id,
                    ),
                )
                created.append(
                    TaskResultResource(
                        resource_id=reference.attachment_id,
                        file_name=reference.file_name,
                        media_type=reference.media_type,
                        size_bytes=reference.size_bytes,
                        sha256=reference.sha256,
                    )
                )
            temporary = manifest.with_suffix(".part")
            temporary.write_text(
                json.dumps(
                    {
                        "task_id": str(task_id),
                        "owner_subject": owner_subject,
                        "conversation_id": conversation_id,
                        "resources": [self._resource_payload(item) for item in created],
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            temporary.replace(manifest)
            return tuple(created)
        except Exception as exc:
            for resource in created:
                self._attachment_storage.discard(
                    resource.resource_id,
                    context=AttachmentAccessContext(
                        subject=owner_subject,
                        conversation_id=conversation_id,
                    ),
                )
            manifest.with_suffix(".part").unlink(missing_ok=True)
            if isinstance(exc, TenderResultResourceStoreError):
                raise
            raise TenderResultResourceStoreError("Tender 结果资源保存失败。") from exc

    def list_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
    ) -> tuple[TaskResultResource, ...] | None:
        if self._attachment_storage is None:
            return None
        manifest = self._resource_manifest_path(task_id)
        data = self._read_resource_data(manifest)
        if data is None:
            return None
        if (
            data.get("owner_subject") != owner_subject
            or data.get("conversation_id") != conversation_id
        ):
            return None
        resources = self._read_resource_manifest(manifest)
        if resources is None:
            return None
        for resource in resources:
            read_result = self._attachment_storage.read(
                resource.resource_id,
                context=AttachmentAccessContext(
                    subject=owner_subject,
                    conversation_id=conversation_id,
                ),
            )
            if (
                read_result.status != "available"
                or read_result.attachment is None
                or read_result.attachment.attachment_id != resource.resource_id
                or read_result.attachment.file_name != resource.file_name
                or read_result.attachment.media_type != resource.media_type
                or read_result.attachment.size_bytes != resource.size_bytes
                or read_result.attachment.sha256 != resource.sha256
            ):
                return None
        return resources

    def _resource_manifest_path(self, task_id: UUID) -> Path:
        return self._resource_root / f"{task_id}.json"

    @staticmethod
    def _read_resource_data(path: Path) -> dict[str, object] | None:
        import json

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _read_resource_manifest(self, path: Path) -> tuple[TaskResultResource, ...] | None:
        data = self._read_resource_data(path)
        raw_resources = data.get("resources") if data is not None else None
        if not isinstance(raw_resources, list) or not raw_resources:
            return None
        try:
            resources = tuple(
                self._resource_from_manifest_item(
                    item,
                )
                for item in raw_resources
            )
        except (KeyError, TypeError, ValueError):
            return None
        return resources

    @staticmethod
    def _resource_from_manifest_item(item: object) -> TaskResultResource:
        if not isinstance(item, dict):
            raise ValueError("Tender 结果资源条目无效。")
        reference = AttachmentRef(
            attachment_id=item["resource_id"],
            file_name=item["file_name"],
            media_type=item["media_type"],
            size_bytes=item["size_bytes"],
            sha256=item["sha256"],
        )
        return TaskResultResource(
            resource_id=reference.attachment_id,
            file_name=reference.file_name,
            media_type=reference.media_type,
            size_bytes=reference.size_bytes,
            sha256=reference.sha256,
        )

    @staticmethod
    def _resource_payload(resource: TaskResultResource) -> dict[str, object]:
        return {
            "resource_id": resource.resource_id,
            "file_name": resource.file_name,
            "media_type": resource.media_type,
            "size_bytes": resource.size_bytes,
            "sha256": resource.sha256,
        }

    def _discard_resources(self, task_id: UUID, owner_subject: str, conversation_id: str) -> None:
        manifest = self._resource_manifest_path(task_id)
        resources = self._read_resource_manifest(manifest) or ()
        if self._attachment_storage is not None:
            for resource in resources:
                self._attachment_storage.discard(
                    resource.resource_id,
                    context=AttachmentAccessContext(
                        subject=owner_subject,
                        conversation_id=conversation_id,
                    ),
                )
        manifest.unlink(missing_ok=True)
        manifest.with_suffix(".part").unlink(missing_ok=True)


__all__ = [
    "AttachmentTenderTaskInputReader",
    "FilesystemTenderTaskResultStore",
    "InMemoryTenderTaskResultStore",
    "TenderTaskInput",
    "TenderTaskInputReaderPort",
    "TenderTaskInputSnapshotPort",
    "TenderTaskResourceStorePort",
    "TenderTaskResultStorePort",
    "TenderResultResourceStoreError",
]
