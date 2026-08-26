from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.platform.interaction.domain.attachment import (
    AttachmentDeclarationError,
    attachment_field_declarations,
)

CapabilityType = Literal["agent", "chat", "knowledge_qa", "policy_decision"]
ConfirmationPolicy = Literal["always", "conditional", "never"]

_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_CAPABILITY_TYPES: frozenset[str] = frozenset(
    {"agent", "chat", "knowledge_qa", "policy_decision"}
)
_CONFIRMATION_POLICIES: frozenset[str] = frozenset(
    {"always", "conditional", "never"}
)


class CapabilityValidationError(ValueError):
    """平台能力目录条目不满足受控契约。"""


@dataclass(frozen=True, slots=True)
class CapabilityPrincipal:
    """调用方已有的权限集合；目录只做权限匹配，不负责身份认证。"""

    permissions: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_permissions(cls, permissions: Collection[str]) -> "CapabilityPrincipal":
        return cls(
            frozenset(permission.strip() for permission in permissions if permission.strip())
        )


@dataclass(frozen=True, slots=True)
class PlatformCapability:
    """平台统一目录中的一项可调用能力。"""

    code: str
    capability_type: CapabilityType
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    required_fields: tuple[str, ...]
    confirmation_policy: ConfirmationPolicy
    permission: tuple[str, ...]
    enabled: bool
    timeout_seconds: int
    error_boundary: str
    dispatch_key: str
    retrieval_metadata: dict[str, object]
    id: int | None = None
    created_at: object | None = None
    updated_at: object | None = None

    def __post_init__(self) -> None:
        validate_capability(self)

    def is_allowed(self, principal: CapabilityPrincipal | None = None) -> bool:
        """判断目录权限是否满足；空权限要求表示平台公开能力。"""

        if not self.permission:
            return True
        return principal is not None and set(self.permission).issubset(principal.permissions)


def validate_capability(capability: PlatformCapability) -> None:
    """执行与数据库约束互补的应用层目录校验。"""

    if not _SAFE_IDENTIFIER.fullmatch(capability.code):
        raise CapabilityValidationError(
            f"能力代码格式无效：{capability.code!r}。只能使用小写字母、数字、点、下划线和短横线。"
        )
    if capability.capability_type not in _CAPABILITY_TYPES:
        raise CapabilityValidationError(f"能力类型无效：{capability.capability_type!r}。")
    if not capability.description.strip():
        raise CapabilityValidationError("能力描述不能为空。")
    if not isinstance(capability.input_schema, dict):
        raise CapabilityValidationError("input_schema 必须是 JSON 对象。")
    try:
        attachment_field_declarations(capability.input_schema)
    except AttachmentDeclarationError as exc:
        raise CapabilityValidationError(f"附件字段声明无效：{exc}") from exc
    if not isinstance(capability.output_schema, dict):
        raise CapabilityValidationError("output_schema 必须是 JSON 对象。")
    if len(set(capability.required_fields)) != len(capability.required_fields):
        raise CapabilityValidationError("required_fields 不能包含重复字段。")
    if any(not field_name.strip() for field_name in capability.required_fields):
        raise CapabilityValidationError("required_fields 不能包含空字段名。")
    properties = capability.input_schema.get("properties")
    if isinstance(properties, Mapping):
        missing_fields = set(capability.required_fields) - set(properties)
        if missing_fields:
            raise CapabilityValidationError(
                f"required_fields 未在 input_schema.properties 中声明：{sorted(missing_fields)}。"
            )
    if capability.confirmation_policy not in _CONFIRMATION_POLICIES:
        raise CapabilityValidationError(
            f"确认策略无效：{capability.confirmation_policy!r}。"
        )
    if any(not permission.strip() for permission in capability.permission):
        raise CapabilityValidationError("permission 不能包含空权限。")
    if capability.timeout_seconds < 1 or capability.timeout_seconds > 3600:
        raise CapabilityValidationError("timeout_seconds 必须在 1 到 3600 秒之间。")
    if not capability.error_boundary.strip():
        raise CapabilityValidationError("error_boundary 不能为空。")
    validate_dispatch_key(capability.dispatch_key)
    if not isinstance(capability.retrieval_metadata, dict):
        raise CapabilityValidationError("retrieval_metadata 必须是 JSON 对象。")


def validate_dispatch_key(dispatch_key: str) -> None:
    """拒绝 URL、类名、函数名和路径等不可控分发目标。"""

    if not _SAFE_IDENTIFIER.fullmatch(dispatch_key):
        raise CapabilityValidationError(
            f"分发键格式无效：{dispatch_key!r}，不得使用 URL、类名、函数名或脚本地址。"
        )
