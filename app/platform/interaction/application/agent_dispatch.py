"""V2 结构化 Agent Call 的策略后受控分发。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from io import BytesIO
from typing import Literal

from pydantic import BaseModel

from app.platform.attachment import AttachmentAccessContext, AttachmentStoragePort
from app.platform.interaction.application.agent_call_policy import (
    AgentCallPolicyCommand,
    AgentCallPolicyResult,
    AgentCallPolicyValidator,
)
from app.platform.interaction.domain.agent_call import (
    AgentCallError,
    AgentCallResult,
    StructuredAgentCall,
)
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.platform.interaction.ports.agent_runtime import AgentRuntimePort
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.security.domain.principal import RequestPrincipal

AgentDispatchStatus = Literal[
    "completed",
    "confirmation_required",
    "rejected",
    "unavailable",
    "failed",
]


@dataclass(frozen=True, slots=True)
class AgentCallDispatchCommand:
    """一次 V2 Agent 调用及其可信主体和可选批准提议。"""

    call: StructuredAgentCall
    principal: RequestPrincipal
    approved_dispatch: ApprovedCapabilityDispatch | None = None


@dataclass(frozen=True, slots=True)
class AgentCallDispatchResult:
    """结构化 Agent 分发的受控结果。"""

    status: AgentDispatchStatus
    call: StructuredAgentCall
    result: AgentCallResult | None = None
    error: AgentCallError | None = None


class AgentCallDispatcher:
    """只执行经策略授权、且仍与当前目录一致的单个 Agent Call。"""

    def __init__(
        self,
        capability_catalog: CapabilityCatalogPort,
        policy_validator: AgentCallPolicyValidator,
        agent_runtime: AgentRuntimePort,
        artifact_storage: AttachmentStoragePort | None = None,
    ) -> None:
        self._capability_catalog = capability_catalog
        self._policy_validator = policy_validator
        self._agent_runtime = agent_runtime
        self._artifact_storage = artifact_storage

    def dispatch(self, command: AgentCallDispatchCommand) -> AgentCallDispatchResult:
        policy = self._policy_validator.validate(
            AgentCallPolicyCommand(
                call=command.call,
                principal=command.principal,
                approved_dispatch=command.approved_dispatch,
            )
        )
        if policy.status != "authorized":
            return _policy_result(policy)

        capability = self._read_current_agent(command)
        if isinstance(capability, AgentCallDispatchResult):
            return capability

        try:
            raw_output = self._agent_runtime.execute(
                capability_code=command.call.capability_code,
                dispatch_key=capability.dispatch_key,
                inputs=dict(command.call.inputs),
                permissions=command.principal.permission_tuple(),
            )
        except LookupError:
            return _error_result(
                command.call,
                status="failed",
                error_code="DISPATCH_TARGET_UNAVAILABLE",
                message="Agent 运行时目标当前不可用，未完成调用。",
            )
        except ValueError:
            return _error_result(
                command.call,
                status="rejected",
                error_code="DISPATCH_INPUT_INVALID",
                message="Agent 调用输入无法构造运行时命令。",
            )
        except Exception:  # noqa: BLE001 - runtime boundary must not leak internals
            return _error_result(
                command.call,
                status="failed",
                error_code="DISPATCH_EXECUTION_FAILED",
                message="Agent 执行失败。",
            )
        try:
            output = _as_json_object(
                raw_output,
                artifact_storage=self._artifact_storage,
                access_context=AttachmentAccessContext(
                    subject=command.principal.subject,
                    conversation_id=command.call.conversation_id,
                ),
            )
        except _ArtifactStorageError:
            return _error_result(
                command.call,
                status="failed",
                error_code="AGENT_ARTIFACT_STORE_FAILED",
                message="Agent 生成文件暂时无法保存。",
            )
        except Exception:  # noqa: BLE001 - output must be safely serializable
            return _error_result(
                command.call,
                status="failed",
                error_code="AGENT_OUTPUT_INVALID",
                message="Agent 返回结果不是受支持的对象。",
            )

        return AgentCallDispatchResult(
            status="completed",
            call=command.call.model_copy(deep=True),
            result=AgentCallResult(
                **_correlation_fields(command.call),
                output=output,
            ),
        )

    def _read_current_agent(
        self,
        command: AgentCallDispatchCommand,
    ) -> PlatformCapability | AgentCallDispatchResult:
        try:
            capability = self._capability_catalog.get_available(
                command.call.capability_code,
                permissions=command.principal.permission_tuple(),
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return _error_result(
                command.call,
                status="unavailable",
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
                message="能力目录暂时不可用，未执行 Agent 调用。",
            )
        if capability is None:
            return _error_result(
                command.call,
                status="rejected",
                error_code="CAPABILITY_UNAVAILABLE",
                message="该 Agent 能力当前不可用，未执行调用。",
            )
        if capability.capability_type != "agent":
            return _error_result(
                command.call,
                status="rejected",
                error_code="CAPABILITY_TYPE_NOT_AGENT",
                message="当前调用目标不是可执行的 Agent 能力。",
            )
        return capability


class _ArtifactStorageError(RuntimeError):
    pass


def _as_json_object(
    value: object,
    *,
    artifact_storage: AttachmentStoragePort | None,
    access_context: AttachmentAccessContext,
) -> dict[str, object]:
    value = _to_python(value)
    if not isinstance(value, Mapping):
        raise TypeError("Agent output must be a JSON object")
    normalized_value = dict(value)
    if artifact_storage is not None:
        normalized_value = _stage_artifacts(
            normalized_value,
            artifact_storage=artifact_storage,
            access_context=access_context,
        )
    value = _json_safe(normalized_value)
    normalized = json.loads(json.dumps(dict(value), ensure_ascii=False, allow_nan=False))
    if not isinstance(normalized, dict):
        raise TypeError("Agent output must be a JSON object")
    return normalized


def _to_python(value: object) -> object:
    """Normalize domain values while preserving transient binary artifacts."""

    if isinstance(value, BaseModel):
        return _to_python(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _to_python(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _to_python(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_python(item) for item in value]
    return value


def _stage_artifacts(
    output: dict[str, object],
    *,
    artifact_storage: AttachmentStoragePort,
    access_context: AttachmentAccessContext,
) -> dict[str, object]:
    staged_ids: list[str] = []
    try:
        artifacts = output.get("artifacts")
        if isinstance(artifacts, list):
            output["artifacts"] = [
                _stage_artifact(
                    artifact,
                    artifact_storage=artifact_storage,
                    access_context=access_context,
                    staged_ids=staged_ids,
                )
                for artifact in artifacts
            ]
        artifact = output.get("artifact")
        if artifact is not None:
            output["artifact"] = _stage_artifact(
                artifact,
                artifact_storage=artifact_storage,
                access_context=access_context,
                staged_ids=staged_ids,
            )
        return output
    except Exception as exc:
        for attachment_id in staged_ids:
            try:
                artifact_storage.discard(attachment_id, context=access_context)
            except Exception:  # noqa: BLE001 - preserve the controlled failure
                pass
        raise _ArtifactStorageError from exc


def _stage_artifact(
    value: object,
    *,
    artifact_storage: AttachmentStoragePort,
    access_context: AttachmentAccessContext,
    staged_ids: list[str],
) -> object:
    if not isinstance(value, Mapping):
        return value
    content = value.get("content")
    if not isinstance(content, bytes):
        return value
    file_name = value.get("file_name")
    media_type = value.get("media_type")
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("artifact file_name is required")
    if not isinstance(media_type, str) or not media_type.strip():
        raise ValueError("artifact media_type is required")
    reference = artifact_storage.stage_attachment(
        file_name=file_name,
        media_type=media_type,
        file_stream=BytesIO(content),
        context=access_context,
    )
    staged_ids.append(reference.attachment_id)
    projected = {str(key): item for key, item in value.items() if key != "content"}
    projected.update(
        {
            "file_name": reference.file_name,
            "media_type": reference.media_type,
            "size": reference.size_bytes,
            "resource_id": reference.attachment_id,
        }
    )
    return projected


def _json_safe(value: object) -> object:
    """Convert staged Agent output to JSON-safe data without retaining bytes."""
    if isinstance(value, bytes):
        return {
            "__agent_bytes__": True,
            "size": len(value),
        }
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported Agent output value: {type(value)!r}")


def _policy_result(policy: AgentCallPolicyResult) -> AgentCallDispatchResult:
    status: AgentDispatchStatus = policy.status
    return _error_result(
        policy.call,
        status=status,
        error_code=policy.error_code or "AGENT_CALL_NOT_AUTHORIZED",
        message=policy.message,
    )


def _error_result(
    call: StructuredAgentCall,
    *,
    status: AgentDispatchStatus,
    error_code: str,
    message: str,
) -> AgentCallDispatchResult:
    return AgentCallDispatchResult(
        status=status,
        call=call.model_copy(deep=True),
        error=AgentCallError(
            **_correlation_fields(call),
            error_code=error_code,
            message=message,
            retryable=False,
        ),
    )


def _correlation_fields(call: StructuredAgentCall) -> dict[str, object]:
    return call.model_dump(mode="python", exclude={"inputs"})


__all__ = [
    "AgentCallDispatchCommand",
    "AgentCallDispatcher",
    "AgentCallDispatchResult",
    "AgentDispatchStatus",
    "AgentRuntimePort",
]
