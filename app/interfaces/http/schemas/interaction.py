from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InteractionIntentRequest(BaseModel):
    """统一入口的自然语言请求与受控业务输入。"""

    model_config = ConfigDict(extra="forbid")

    user_input: str = Field(min_length=1, max_length=10_000)
    provided_inputs: dict[str, object] = Field(default_factory=dict)
    conversation_id: UUID | None = None


class InteractionChatRequest(BaseModel):
    """Chat 接受用户文本、附件等原始上下文，不接受调用授权字段。"""

    model_config = ConfigDict(extra="forbid")

    user_input: str = Field(min_length=1, max_length=10_000)
    provided_inputs: dict[str, object] = Field(default_factory=dict)
    conversation_id: UUID | None = None


class InteractionConfirmationRequest(BaseModel):
    """只允许明确的确认或取消动作。"""

    model_config = ConfigDict(extra="forbid")

    action: Literal["confirm", "cancel"]


class InteractionProposalResponse(BaseModel):
    """客户端确认所需的最小提议信息，不暴露分发目标或完整输入。"""

    proposal_id: str
    state: Literal["pending", "confirmed", "cancelled"]
    capability_code: str
    summary: str
    confirmation_prompt: str


class InteractionAssessmentResponse(BaseModel):
    """A browser-safe view of an intent assessment."""

    status: Literal["matched", "needs_clarification", "unrecognized"]
    capability_code: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    clarification: str | None = None
    confidence: float | None = None
    error_code: str | None = None


class InteractionGatewayResponse(BaseModel):
    """统一入口返回的受控交互状态。"""

    status: Literal[
        "needs_clarification",
        "unrecognized",
        "authorized",
        "pending",
        "cancelled",
        "completed",
        "rejected",
        "failed",
    ]
    message: str
    assessment: InteractionAssessmentResponse | None = None
    proposal: InteractionProposalResponse | None = None
    execution_result: dict[str, Any] | None = None
    error_code: str | None = None
    conversation_id: UUID | None = None
