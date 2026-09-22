"""Tender 异步 Task 所需的业务端口。"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.business.agents.tender.contracts import TenderGenerateSkeletonResult
from app.business.agents.tender.errors import TenderResultResourceStoreError
from app.platform.attachment.contracts import AttachmentAccessContext
from app.platform.attachment.ports.storage_port import AttachmentStoragePort
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.task.ports import TaskResultResource, TaskResultResourceReaderPort


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


class TenderTaskResourceStorePort(TenderTaskResultStorePort, TaskResultResourceReaderPort, Protocol):
    """保存并读取已绑定 Conversation 的 Tender 结果资源。"""

    def save_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
        result: TenderGenerateSkeletonResult,
    ) -> tuple[TaskResultResource, ...]: ...


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


class InMemoryTenderTaskResultStore(TenderTaskResourceStorePort):
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

    def save_resources(self, *, task_id: UUID, owner_subject: str, conversation_id: str, result: TenderGenerateSkeletonResult) -> tuple[TaskResultResource, ...]:
        existing = self.resources.get(task_id)
        if existing is not None:
            if self._resource_contexts.get(task_id) != (owner_subject, conversation_id):
                raise TenderResultResourceStoreError("Tender 结果资源归属不一致。")
            try:
                expected = self._resource_metadata(result, task_id=task_id)
            except (TypeError, ValueError) as exc:
                raise TenderResultResourceStoreError("Tender 结果资源元数据无效。") from exc
            if existing != expected:
                raise TenderResultResourceStoreError("Tender 结果资源元数据不一致。")
            return existing
        try:
            resources = self._resource_metadata(result, task_id=task_id)
        except (TypeError, ValueError) as exc:
            raise TenderResultResourceStoreError("Tender 结果资源元数据无效。") from exc
        if not resources:
            raise TenderResultResourceStoreError("Tender 结果缺少可交付文件。")
        self.resources[task_id] = resources
        self._resource_contexts[task_id] = (owner_subject, conversation_id)
        return resources

    @staticmethod
    def _resource_metadata(
        result: TenderGenerateSkeletonResult,
        *,
        task_id: UUID | None = None,
    ) -> tuple[TaskResultResource, ...]:
        resources: list[TaskResultResource] = []
        for index, artifact in enumerate(result.artifacts):
            if not artifact.content:
                raise ValueError("Tender 结果缺少可交付文件。")
            resources.append(
                TaskResultResource(
                    resource_id=(f"memory:{task_id}:{index}" if task_id is not None else ""),
                    file_name=artifact.file_name,
                    media_type=artifact.media_type,
                    size_bytes=len(artifact.content),
                    sha256=hashlib.sha256(artifact.content).hexdigest(),
                )
            )
        return tuple(resources)

    def list_resources(self, *, task_id: UUID, owner_subject: str, conversation_id: str) -> tuple[TaskResultResource, ...] | None:
        if self._resource_contexts.get(task_id) != (owner_subject, conversation_id):
            return None
        return self.resources.get(task_id)


class FilesystemTenderTaskResultStore(TenderTaskResourceStorePort):
    """保存内部结果，并将会话绑定文件映射为 Attachment 资源。"""

    def __init__(self, workspace_root: Path, *, attachment_storage: AttachmentStoragePort | None = None) -> None:
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
        target = self._root / f"{task_id}.json"
        resources = None
        if self._attachment_storage is not None and conversation_id:
            resources = self.save_resources(
                task_id=task_id,
                owner_subject=owner_subject,
                conversation_id=conversation_id,
                result=result,
            )
        if target.exists():
            existing = self._read_json(target)
            if not existing or existing.get("task_id") != str(task_id) or existing.get("owner_subject") != owner_subject:
                raise TenderResultResourceStoreError("Tender 内部结果归属不一致。")
            return f"tender-result:{task_id}"
        payload = {
            "task_id": str(task_id),
            "owner_subject": owner_subject,
            "analysis": result.analysis.model_dump(mode="json"),
            "model": result.model,
            "prompt_version": result.prompt_version,
        }
        if resources is None:
            payload["artifacts"] = [
                {
                    "file_name": artifact.file_name,
                    "media_type": artifact.media_type,
                    "content_base64": base64.b64encode(artifact.content).decode("ascii"),
                }
                for artifact in result.artifacts
            ]
        else:
            payload["resources"] = [self._resource_payload(item) for item in resources]
        temporary = target.with_suffix(".part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return f"tender-result:{task_id}"

    def save_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
        result: TenderGenerateSkeletonResult,
    ) -> tuple[TaskResultResource, ...]:
        if self._attachment_storage is None or not conversation_id.strip():
            raise TenderResultResourceStoreError("Tender 结果资源依赖或 Conversation 绑定缺失。")
        manifest = self._resource_root / f"{task_id}.json"
        if manifest.exists():
            data = self._read_json(manifest)
            if (
                data
                and data.get("task_id") == str(task_id)
                and data.get("owner_subject") == owner_subject
                and data.get("conversation_id") == conversation_id
            ):
                try:
                    existing = self._read_manifest_resources(data)
                    expected = self._expected_resource_metadata(result)
                except (KeyError, TypeError, ValueError) as exc:
                    raise TenderResultResourceStoreError("Tender 结果资源清单无效。") from exc
                if tuple(self._resource_identity(item) for item in existing) != tuple(
                    self._resource_identity(item) for item in expected
                ):
                    raise TenderResultResourceStoreError("Tender 结果资源元数据不一致。")
                try:
                    self._validate_stored_resources(existing, owner_subject, conversation_id)
                except (OSError, TypeError, ValueError) as exc:
                    raise TenderResultResourceStoreError("Tender 结果资源附件不可用。") from exc
                return existing
            raise TenderResultResourceStoreError("Tender 结果资源清单无效。")

        created: list[TaskResultResource] = []
        try:
            for artifact in result.artifacts:
                if not artifact.content:
                    raise TenderResultResourceStoreError("Tender 结果缺少可交付文件。")
                reference = self._attachment_storage.stage_attachment(
                    file_name=artifact.file_name,
                    media_type=artifact.media_type,
                    file_stream=io.BytesIO(artifact.content),
                    context=AttachmentAccessContext(subject=owner_subject, conversation_id=conversation_id),
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
                    {"task_id": str(task_id), "owner_subject": owner_subject, "conversation_id": conversation_id, "resources": [self._resource_payload(item) for item in created]},
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
                    context=AttachmentAccessContext(subject=owner_subject, conversation_id=conversation_id),
                )
            manifest.with_suffix(".part").unlink(missing_ok=True)
            if isinstance(exc, TenderResultResourceStoreError):
                raise
            raise TenderResultResourceStoreError("Tender 结果资源写入失败。") from exc

    def list_resources(
        self,
        *,
        task_id: UUID,
        owner_subject: str,
        conversation_id: str,
    ) -> tuple[TaskResultResource, ...] | None:
        if self._attachment_storage is None:
            return None
        data = self._read_json(self._resource_root / f"{task_id}.json")
        if (
            not data
            or data.get("task_id") != str(task_id)
            or data.get("owner_subject") != owner_subject
            or data.get("conversation_id") != conversation_id
        ):
            return None
        try:
            resources = self._read_manifest_resources(data)
        except (KeyError, TypeError, ValueError):
            return None
        for resource in resources:
            read_result = self._attachment_storage.read(
                resource.resource_id,
                context=AttachmentAccessContext(subject=owner_subject, conversation_id=conversation_id),
            )
            if (
                read_result.status != "available"
                or read_result.attachment is None
                or read_result.attachment.file_name != resource.file_name
                or read_result.attachment.media_type != resource.media_type
                or read_result.attachment.sha256 != resource.sha256
                or read_result.attachment.size_bytes != resource.size_bytes
            ):
                return None
        return resources

    def _validate_stored_resources(
        self,
        resources: tuple[TaskResultResource, ...],
        owner_subject: str,
        conversation_id: str,
    ) -> None:
        for resource in resources:
            read_result = self._attachment_storage.read(
                resource.resource_id,
                context=AttachmentAccessContext(subject=owner_subject, conversation_id=conversation_id),
            )
            if (
                read_result.status != "available"
                or read_result.attachment is None
                or read_result.attachment.file_name != resource.file_name
                or read_result.attachment.media_type != resource.media_type
                or read_result.attachment.sha256 != resource.sha256
                or read_result.attachment.size_bytes != resource.size_bytes
            ):
                raise ValueError("Tender 结果资源附件不可用。")

    @staticmethod
    def _expected_resource_metadata(result: TenderGenerateSkeletonResult) -> tuple[TaskResultResource, ...]:
        expected: list[TaskResultResource] = []
        for artifact in result.artifacts:
            if not artifact.content:
                raise ValueError("Tender 结果缺少可交付文件。")
            expected.append(
                TaskResultResource(
                    resource_id="expected",
                    file_name=artifact.file_name,
                    media_type=artifact.media_type,
                    size_bytes=len(artifact.content),
                    sha256=hashlib.sha256(artifact.content).hexdigest(),
                )
            )
        return tuple(expected)

    @staticmethod
    def _resource_identity(resource: TaskResultResource) -> tuple[str, str, int, str]:
        return (resource.file_name, resource.media_type, resource.size_bytes, resource.sha256)

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _read_manifest_resources(data: dict[str, object]) -> tuple[TaskResultResource, ...]:
        raw = data.get("resources")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Tender 结果资源清单无效。")
        if any(not isinstance(item, dict) for item in raw):
            raise ValueError("Tender 结果资源清单无效。")
        return tuple(
            TaskResultResource(
                resource_id=str(item["resource_id"]),
                file_name=str(item["file_name"]),
                media_type=str(item["media_type"]),
                size_bytes=int(item["size_bytes"]),
                sha256=str(item["sha256"]),
            )
            for item in raw
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


__all__ = [
    "AttachmentTenderTaskInputReader",
    "FilesystemTenderTaskResultStore",
    "InMemoryTenderTaskResultStore",
    "TenderTaskInput",
    "TenderTaskInputReaderPort",
    "TenderTaskInputSnapshotPort",
    "TenderTaskResultStorePort",
    "TenderTaskResourceStorePort",
]
