"""LLM、交互网关与 Agent Runtime 之间的结构化调用契约。"""

from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class _AgentCallContract(BaseModel):
    """共享的关联字段和领域边界配置。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1)
    capability_code: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1)
    turn_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    parent_run_id: str | None = Field(default=None, min_length=1)

    _identifier_fields: ClassVar[tuple[str, ...]] = (
        "call_id",
        "capability_code",
        "conversation_id",
        "turn_id",
        "run_id",
        "parent_run_id",
    )

    @field_validator(*_identifier_fields, mode="before")
    @classmethod
    def _validate_identifier(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("调用关联标识必须是非空字符串。")
        return value.strip()


class StructuredAgentCall(_AgentCallContract):
    """模型或上层编排产生的单次 Agent 调用数据。"""

    inputs: dict[str, object] = Field(default_factory=dict)


class AgentCallResult(_AgentCallContract):
    """Agent Runtime 成功返回的结构化业务结果。"""

    output: dict[str, object] = Field(default_factory=dict)


class AgentCallError(_AgentCallContract):
    """Agent Runtime 对外返回的受控失败结果。"""

    error_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False

    @field_validator("error_code", mode="before")
    @classmethod
    def _validate_error_code(cls, value: object) -> object:
        if not isinstance(value, str) or not _SAFE_ERROR_CODE.fullmatch(value.strip()):
            raise ValueError("错误码必须是大写字母、数字和下划线组成的稳定标识。")
        return value.strip()

    @field_validator("message", mode="before")
    @classmethod
    def _validate_message(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("错误消息必须是非空字符串。")
        return value.strip()


__all__ = ["AgentCallError", "AgentCallResult", "StructuredAgentCall"]
