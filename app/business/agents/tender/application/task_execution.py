"""Tender Agent 的受控异步 Task 快照与执行器。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from app.business.agents.tender.application.service import TenderApplication
from app.business.agents.tender.contracts import TenderGenerateSkeletonCommand
from app.business.agents.tender.errors import (
    TenderAnalysisError,
    TenderDocumentParseError,
    TenderInputError,
    TenderRenderError,
)
from app.business.agents.tender.ports.task_port import (
    TenderTaskInput,
    TenderTaskInputReaderPort,
    TenderTaskResultStorePort,
)
from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.attachment import ResolvedAttachment
from app.platform.interaction.ports.agent_task_bridge import (
    AgentTaskInputSnapshot,
    AgentTaskInputSnapshotPort,
    AgentTaskProfile,
)
from app.platform.task.domain import FailureCategory
from app.platform.task.ports.worker import (
    TaskExecutionCancellation,
    TaskExecutionContext,
    TaskExecutionFailure,
    TaskExecutionSuccess,
)
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class TenderTaskInputSnapshotProvider(AgentTaskInputSnapshotPort):
    """把已解析附件转换为确定性快照事实，不保存文档字节。"""

    def snapshot(
        self,
        call: StructuredAgentCall,
        profile: AgentTaskProfile,
    ) -> AgentTaskInputSnapshot:
        source = call.inputs.get("source_document")
        if not isinstance(source, ResolvedAttachment):
            raise ValueError("异步 Tender 必须使用已解析附件。")
        user_focus = call.inputs.get("user_focus")
        if user_focus is not None and not isinstance(user_focus, str):
            raise ValueError("用户关注点格式无效。")
        normalized_focus = user_focus.strip() if isinstance(user_focus, str) else None
        reference = source.reference
        snapshot = TenderTaskInput(
            attachment_id=reference.attachment_id,
            file_name=reference.file_name,
            media_type=reference.media_type,
            sha256=reference.sha256,
            user_focus=normalized_focus or None,
            conversation_id=call.conversation_id,
        )
        canonical = json.dumps(
            {
                "attachment_id": snapshot.attachment_id,
                "file_name": snapshot.file_name,
                "media_type": snapshot.media_type,
                "sha256": snapshot.sha256,
                "user_focus": snapshot.user_focus,
                "conversation_id": snapshot.conversation_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        metadata = {
            "snapshot_reference": snapshot.attachment_id,
            "file_name": snapshot.file_name,
            "media_type": snapshot.media_type,
            "sha256": snapshot.sha256,
        }
        if snapshot.user_focus is not None:
            metadata["user_focus"] = snapshot.user_focus
        if snapshot.conversation_id is not None:
            metadata["conversation_id"] = snapshot.conversation_id
        return AgentTaskInputSnapshot(
            input_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            snapshot_reference=snapshot.attachment_id,
            display_metadata=metadata,
        )


class TenderTaskExecutor:
    """固定 task type 的 Tender 执行器，只通过 Worker 上下文回写结果。"""

    retry_delay = timedelta(minutes=1)

    def __init__(
        self,
        *,
        application: TenderApplication,
        input_reader: TenderTaskInputReaderPort,
        result_store: TenderTaskResultStorePort,
        clock=None,  # noqa: ANN001 - composition injects a deterministic clock in tests
    ) -> None:
        self._application = application
        self._input_reader = input_reader
        self._result_store = result_store
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        context: TaskExecutionContext,
    ) -> TaskExecutionSuccess | TaskExecutionFailure | TaskExecutionCancellation:
        if context.is_cancel_requested is not None and context.is_cancel_requested():
            return TaskExecutionCancellation()
        try:
            snapshot = _snapshot_from_context(context)
            content = self._input_reader.read(snapshot, owner_subject=context.owner_subject)
            if context.is_cancel_requested is not None and context.is_cancel_requested():
                return TaskExecutionCancellation()
            context.renew_lease()
            result = self._application.execute(
                TenderGenerateSkeletonCommand(
                    file_name=snapshot.file_name,
                    content=content,
                    user_focus=snapshot.user_focus,
                )
            )
            if context.is_cancel_requested is not None and context.is_cancel_requested():
                return TaskExecutionCancellation()
            self._result_store.save(
                task_id=context.task_id,
                owner_subject=context.owner_subject,
                result=result,
            )
            fingerprint = _result_fingerprint(result)
            return TaskExecutionSuccess(
                result_fingerprint=fingerprint,
                result_summary=f"Tender 投标骨架已生成（{len(result.artifacts)} 个文件）。",
            )
        except (TenderInputError, TenderDocumentParseError, TenderAnalysisError, TenderRenderError):
            return _permanent_failure("TENDER_INPUT_OR_RESULT_INVALID")
        except ServiceNotConfiguredError:
            return _permanent_failure("TENDER_SERVICE_NOT_CONFIGURED")
        except UpstreamServiceError:
            return TaskExecutionFailure(
                failure_category=FailureCategory.TRANSIENT,
                failure_code="TENDER_UPSTREAM_FAILED",
                result_fingerprint="tender-upstream-failed",
                retry_at=self._clock().astimezone(UTC) + self.retry_delay,
            )
        except ValueError:
            return _permanent_failure("TENDER_INPUT_SNAPSHOT_UNAVAILABLE")
        except Exception:  # noqa: BLE001 - worker boundary must not leak details
            return _permanent_failure("TENDER_EXECUTION_FAILED")


def _snapshot_from_context(context: TaskExecutionContext) -> TenderTaskInput:
    metadata = context.display_metadata
    required = ("snapshot_reference", "file_name", "media_type", "sha256")
    if any(
        not isinstance(metadata.get(field), str) or not metadata[field].strip()
        for field in required
    ):
        raise ValueError("Tender Task 快照元数据不完整。")
    return TenderTaskInput(
        attachment_id=metadata["snapshot_reference"],
        file_name=metadata["file_name"],
        media_type=metadata["media_type"],
        sha256=metadata["sha256"],
        user_focus=metadata.get("user_focus"),
        conversation_id=metadata.get("conversation_id"),
    )


def _result_fingerprint(result: object) -> str:
    payload = {
        "analysis": result.analysis.model_dump(mode="json"),
        "model": result.model,
        "prompt_version": result.prompt_version,
        "artifacts": [
            {
                "file_name": artifact.file_name,
                "media_type": artifact.media_type,
                "content_sha256": hashlib.sha256(artifact.content).hexdigest(),
            }
            for artifact in result.artifacts
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _permanent_failure(code: str) -> TaskExecutionFailure:
    return TaskExecutionFailure(
        failure_category=FailureCategory.PERMANENT,
        failure_code=code,
        result_fingerprint=code.lower(),
    )


__all__ = ["TenderTaskExecutor", "TenderTaskInputSnapshotProvider"]
