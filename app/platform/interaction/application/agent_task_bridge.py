"""经授权 Agent 调用到 Task 的受控桥接。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.ports.agent_execution import (
    AgentExecutionCommand,
    AgentExecutionOutcome,
    AgentExecutionStrategyPort,
)
from app.platform.interaction.ports.agent_task_bridge import (
    AgentTaskInputSnapshot,
    AgentTaskInputSnapshotPort,
    AgentTaskProfile,
    AgentTaskProfileRegistryPort,
    AgentTaskRoute,
)
from app.platform.task.application.trusted_submission import TrustedTaskSubmissionCommand
from app.platform.task.errors import (
    TaskIdempotencyConflictError,
    TaskSubmissionPolicyError,
    TaskSubmissionPrincipalError,
)

_SAFE_CALL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class AgentTaskProfileRegistry(AgentTaskProfileRegistryPort):
    """Composition 创建的一次性异步路由快照，不提供运行时注册。"""

    def __init__(self, routes: Iterable[AgentTaskRoute] = ()) -> None:
        normalized: dict[str, AgentTaskRoute] = {}
        for route in routes:
            code = route.profile.capability_code
            if code in normalized:
                raise ValueError("同一能力不能重复绑定异步 Task 档案。")
            normalized[code] = route
        self._routes = normalized

    def get(self, capability_code: str) -> AgentTaskRoute | None:
        return self._routes.get(capability_code)


class AgentTaskBridge(AgentExecutionStrategyPort):
    """只通过受信任提交端口创建 Task，并返回不透明执行引用。"""

    def __init__(
        self,
        profile_registry: AgentTaskProfileRegistryPort,
        snapshot_provider: AgentTaskInputSnapshotPort,
    ) -> None:
        self._profile_registry = profile_registry
        self._snapshot_provider = snapshot_provider

    def execute(self, command: AgentExecutionCommand) -> AgentExecutionOutcome:
        route = self._profile_registry.get(command.capability.code)
        if route is None:
            return AgentExecutionOutcome.failed(
                error_code="ASYNC_PROFILE_UNAVAILABLE",
                message="当前 Agent 能力未配置异步任务档案。",
            )
        if not _route_matches(command, route):
            return AgentExecutionOutcome.failed(
                error_code="ASYNC_PROFILE_INVALID",
                message="当前 Agent 能力的异步任务档案不可用。",
            )
        try:
            snapshot = self._snapshot_provider.snapshot(command.call, route.profile)
            _validate_snapshot(snapshot, route.profile)
            idempotency_key = _idempotency_key(
                command.call.capability_code,
                command.call.call_id,
            )
        except ValueError:
            return AgentExecutionOutcome.failed(
                error_code="ASYNC_INPUT_INVALID",
                message="异步 Agent 输入无法生成安全任务快照。",
            )
        except Exception:  # noqa: BLE001 - snapshot boundary must not leak details
            return AgentExecutionOutcome.failed(
                error_code="ASYNC_INPUT_SNAPSHOT_FAILED",
                message="异步 Agent 输入快照暂时不可用。",
            )

        try:
            task = route.submission.submit(
                command.principal,
                TrustedTaskSubmissionCommand(
                    idempotency_key=idempotency_key,
                    input_fingerprint=snapshot.input_fingerprint,
                    display_metadata=dict(snapshot.display_metadata),
                ),
            )
        except TaskIdempotencyConflictError:
            return AgentExecutionOutcome.failed(
                error_code="TASK_IDEMPOTENCY_CONFLICT",
                message="同一 Agent 调用使用了不同的任务输入。",
            )
        except TaskSubmissionPrincipalError:
            return AgentExecutionOutcome.failed(
                error_code="TASK_SUBMISSION_PRINCIPAL_INVALID",
                message="当前主体不能提交异步任务。",
            )
        except TaskSubmissionPolicyError:
            return AgentExecutionOutcome.failed(
                error_code="TASK_SUBMISSION_POLICY_INVALID",
                message="异步任务提交不符合服务端策略。",
            )
        except Exception:  # noqa: BLE001 - Task boundary must not leak internals
            return AgentExecutionOutcome.failed(
                error_code="TASK_SUBMISSION_FAILED",
                message="异步任务暂时无法提交。",
                retryable=True,
            )
        return AgentExecutionOutcome.accepted(f"task:{task.id}")


class AgentTaskExecutionStrategyRouter(AgentExecutionStrategyPort):
    """按服务端异步档案固定选择桥接或同步策略。"""

    def __init__(
        self,
        profile_registry: AgentTaskProfileRegistryPort,
        synchronous_strategy: AgentExecutionStrategyPort,
        task_bridge: AgentTaskBridge,
    ) -> None:
        self._profile_registry = profile_registry
        self._synchronous_strategy = synchronous_strategy
        self._task_bridge = task_bridge

    def execute(self, command: AgentExecutionCommand) -> AgentExecutionOutcome:
        try:
            route = self._profile_registry.get(command.capability.code)
        except Exception:  # noqa: BLE001 - fixed configuration boundary
            return AgentExecutionOutcome.failed(
                error_code="ASYNC_PROFILE_UNAVAILABLE",
                message="异步任务配置暂时不可用。",
            )
        if route is None:
            return self._synchronous_strategy.execute(command)
        return self._task_bridge.execute(command)


class UnconfiguredAgentTaskInputSnapshotProvider(AgentTaskInputSnapshotPort):
    """生产默认空档案的拒绝实现；真实快照由后续业务 Change 注入。"""

    def snapshot(
        self,
        call: StructuredAgentCall,
        profile: AgentTaskProfile,
    ) -> AgentTaskInputSnapshot:
        raise ValueError("异步输入快照尚未配置。")


class CanonicalAgentTaskInputSnapshotProvider(AgentTaskInputSnapshotPort):
    """使用有限 JSON 输入生成确定性指纹，不持久化原始调用参数。"""

    def snapshot(
        self,
        call: StructuredAgentCall,
        profile: AgentTaskProfile,
    ) -> AgentTaskInputSnapshot:
        try:
            canonical = json.dumps(
                call.inputs,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Agent 输入必须是有限的 JSON 值。") from exc
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        metadata = {}
        if "call_id" in profile.display_metadata_fields:
            metadata["call_id"] = call.call_id
        return AgentTaskInputSnapshot(
            input_fingerprint=fingerprint,
            display_metadata=metadata,
        )


def _route_matches(command: AgentExecutionCommand, route: AgentTaskRoute) -> bool:
    profile: AgentTaskProfile = route.profile
    return (
        command.capability.capability_type == "agent"
        and command.capability.enabled
        and command.call.capability_code == profile.capability_code
        and command.capability.code == profile.capability_code
    )


def _validate_snapshot(
    snapshot: AgentTaskInputSnapshot,
    profile: AgentTaskProfile,
) -> None:
    if not isinstance(snapshot, AgentTaskInputSnapshot):
        raise ValueError("快照事实类型无效。")
    if any(
        field_name not in profile.display_metadata_fields
        for field_name in snapshot.display_metadata
    ):
        raise ValueError("快照展示字段超出服务端白名单。")


def _idempotency_key(capability_code: str, call_id: str) -> str:
    if not _SAFE_CALL_ID.fullmatch(call_id):
        raise ValueError("调用关联标识包含不安全字符。")
    return f"agent:{capability_code}:{call_id}"


__all__ = [
    "AgentTaskBridge",
    "AgentTaskExecutionStrategyRouter",
    "AgentTaskProfileRegistry",
    "CanonicalAgentTaskInputSnapshotProvider",
    "UnconfiguredAgentTaskInputSnapshotProvider",
]
