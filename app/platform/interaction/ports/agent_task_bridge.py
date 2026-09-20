"""Agent 调用桥接到 Task 的协议无关端口。"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.security.domain.principal import RequestPrincipal
from app.platform.task.application.contracts import TaskView
from app.platform.task.application.trusted_submission import (
    TrustedTaskSubmissionCommand,
    TrustedTaskSubmissionProfile,
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}必须是非空字符串。")
    return value.strip()


@dataclass(frozen=True, slots=True)
class AgentTaskProfile:
    """由 Composition 固定的单项异步 Task 提交档案。"""

    capability_code: str
    task_type: str
    max_attempts: int
    allow_manual_retry: bool = True
    display_metadata_fields: Collection[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_code", _require_text(self.capability_code, "能力代码"))
        object.__setattr__(self, "task_type", _require_text(self.task_type, "任务类型"))
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts <= 0
        ):
            raise ValueError("最大尝试次数必须是正整数。")
        if not isinstance(self.allow_manual_retry, bool):
            raise ValueError("手动重试策略必须是布尔值。")
        if isinstance(self.display_metadata_fields, str) or not isinstance(
            self.display_metadata_fields, Collection
        ):
            raise ValueError("展示字段白名单必须是字符串集合。")
        object.__setattr__(
            self,
            "display_metadata_fields",
            frozenset(
                _require_text(field_name, "展示字段名")
                for field_name in self.display_metadata_fields
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentTaskInputSnapshot:
    """快照规范化后的安全事实；不携带原始 Agent 输入。"""

    input_fingerprint: str
    snapshot_reference: str | None = None
    display_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_fingerprint",
            _require_text(self.input_fingerprint, "输入指纹"),
        )
        if self.snapshot_reference is not None:
            object.__setattr__(
                self,
                "snapshot_reference",
                _require_text(self.snapshot_reference, "快照引用"),
            )
        if not isinstance(self.display_metadata, Mapping):
            raise ValueError("展示元数据必须是键值映射。")
        object.__setattr__(
            self,
            "display_metadata",
            {
                _require_text(key, "展示字段名"): _require_text(value, "展示字段值")
                for key, value in self.display_metadata.items()
            },
        )


class AgentTaskSubmissionPort(Protocol):
    """受信任 Task 提交 Application 的最小结构化端口。"""

    @property
    def profile(self) -> TrustedTaskSubmissionProfile: ...

    def submit(
        self,
        principal: RequestPrincipal,
        command: TrustedTaskSubmissionCommand,
    ) -> TaskView: ...


class AgentTaskInputSnapshotPort(Protocol):
    """将已授权调用转换为不含原文的输入快照事实。"""

    def snapshot(
        self,
        call: StructuredAgentCall,
        profile: AgentTaskProfile,
    ) -> AgentTaskInputSnapshot: ...


@dataclass(frozen=True, slots=True)
class AgentTaskRoute:
    """异步能力、固定档案与受信任提交器的服务端绑定。"""

    profile: AgentTaskProfile
    submission: AgentTaskSubmissionPort

    def __post_init__(self) -> None:
        if not isinstance(self.profile, AgentTaskProfile):
            raise ValueError("异步 Task 路由必须包含有效档案。")
        if not hasattr(self.submission, "submit") or not hasattr(self.submission, "profile"):
            raise ValueError("异步 Task 路由必须绑定受信任提交能力。")
        submission_profile = self.submission.profile
        if not isinstance(submission_profile, TrustedTaskSubmissionProfile):
            raise ValueError("异步 Task 路由的提交档案无效。")
        if (
            submission_profile.task_type != self.profile.task_type
            or submission_profile.max_attempts != self.profile.max_attempts
            or submission_profile.allow_manual_retry != self.profile.allow_manual_retry
            or submission_profile.display_metadata_fields
            != self.profile.display_metadata_fields
        ):
            raise ValueError("异步 Task 档案与受信任提交策略不一致。")


class AgentTaskProfileRegistryPort(Protocol):
    """服务端固定的异步能力注册表。"""

    def get(self, capability_code: str) -> AgentTaskRoute | None: ...


__all__ = [
    "AgentTaskInputSnapshot",
    "AgentTaskInputSnapshotPort",
    "AgentTaskProfile",
    "AgentTaskProfileRegistryPort",
    "AgentTaskRoute",
    "AgentTaskSubmissionPort",
]
