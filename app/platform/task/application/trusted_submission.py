from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from app.platform.security.domain import RequestPrincipal
from app.platform.task.application.contracts import SubmitTaskCommand, TaskView
from app.platform.task.application.lifecycle_service import TaskLifecycleService
from app.platform.task.errors import TaskSubmissionPolicyError, TaskSubmissionPrincipalError


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskSubmissionPolicyError(f"{label}必须是非空字符串。")
    return value.strip()


@dataclass(frozen=True, slots=True)
class TrustedTaskSubmissionProfile:
    """由 Composition 为单个受信任生产者固定的任务提交策略。"""

    task_type: str
    max_attempts: int
    allow_manual_retry: bool = True
    display_metadata_fields: Collection[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_type", _require_text(self.task_type, "任务类型"))
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts <= 0
        ):
            raise TaskSubmissionPolicyError("最大尝试次数必须是正整数。")
        if not isinstance(self.allow_manual_retry, bool):
            raise TaskSubmissionPolicyError("手动重试策略必须是布尔值。")
        if isinstance(self.display_metadata_fields, str) or not isinstance(
            self.display_metadata_fields, Collection
        ):
            raise TaskSubmissionPolicyError("展示字段白名单必须是字符串集合。")
        fields = frozenset(
            _require_text(field_name, "展示字段名")
            for field_name in self.display_metadata_fields
        )
        object.__setattr__(self, "display_metadata_fields", fields)


@dataclass(frozen=True, slots=True)
class TrustedTaskSubmissionCommand:
    """业务生产者提供的最小提交事实，不携带可覆盖策略或归属的字段。"""

    idempotency_key: str
    input_fingerprint: str
    display_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "idempotency_key",
            _require_text(self.idempotency_key, "幂等键"),
        )
        object.__setattr__(
            self,
            "input_fingerprint",
            _require_text(self.input_fingerprint, "输入指纹"),
        )
        if not isinstance(self.display_metadata, Mapping):
            raise TaskSubmissionPolicyError("展示元数据必须是键值映射。")
        object.__setattr__(self, "display_metadata", dict(self.display_metadata))


class TrustedTaskSubmissionService:
    """只允许服务端可信主体按固定档案创建 Task 的 Application 能力。"""

    def __init__(
        self,
        lifecycle_service: TaskLifecycleService,
        profile: TrustedTaskSubmissionProfile,
    ) -> None:
        self._lifecycle_service = lifecycle_service
        self._profile = profile

    @property
    def profile(self) -> TrustedTaskSubmissionProfile:
        """只读暴露固定档案，供服务端 Composition 校验跨能力绑定。"""

        return self._profile

    def submit(
        self,
        principal: RequestPrincipal,
        command: TrustedTaskSubmissionCommand,
    ) -> TaskView:
        """从可信主体和固定档案构造低层命令，禁止调用方覆盖归属与策略。"""

        owner_subject = self._owner_subject(principal)
        display_metadata = self._display_metadata(command.display_metadata)
        return self._lifecycle_service.submit(
            SubmitTaskCommand(
                owner_subject=owner_subject,
                task_type=self._profile.task_type,
                idempotency_key=command.idempotency_key,
                input_fingerprint=command.input_fingerprint,
                max_attempts=self._profile.max_attempts,
                display_metadata=display_metadata,
                allow_manual_retry=self._profile.allow_manual_retry,
            )
        )

    @staticmethod
    def _owner_subject(principal: RequestPrincipal) -> str:
        if not isinstance(principal, RequestPrincipal) or not principal.authenticated:
            raise TaskSubmissionPrincipalError("只有已认证主体可以提交任务。")
        subject = principal.subject.strip() if isinstance(principal.subject, str) else ""
        if not subject:
            raise TaskSubmissionPrincipalError("可信主体必须包含非空 subject。")
        return subject

    def _display_metadata(self, metadata: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in metadata.items():
            field_name = _require_text(key, "展示字段名")
            if field_name not in self._profile.display_metadata_fields:
                raise TaskSubmissionPolicyError("展示元数据包含当前提交档案未声明的字段。")
            normalized[field_name] = _require_text(value, "展示字段值")
        return normalized
