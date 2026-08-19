from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.modules.interaction.domain.capability import CapabilityType

ConfirmationProposalState = Literal["pending", "confirmed", "cancelled"]
ConfirmationResultStatus = Literal["pending", "confirmed", "cancelled", "rejected"]


class ConfirmationProposal(BaseModel):
    """当前请求生命周期内的待确认提议，不包含执行器引用。"""

    proposal_id: str = Field(min_length=1)
    state: ConfirmationProposalState = "pending"
    capability_code: str = Field(min_length=1)
    capability_type: CapabilityType = "chat"
    dispatch_key: str = Field(min_length=1)
    inputs: dict[str, object] = Field(default_factory=dict)
    summary: str = Field(min_length=1)
    confirmation_prompt: str = Field(min_length=1)


class ApprovedCapabilityDispatch(BaseModel):
    """用户确认后的受控提议，仅供后续 Dispatcher 消费。"""

    proposal_id: str = Field(min_length=1)
    capability_code: str = Field(min_length=1)
    dispatch_key: str = Field(min_length=1)
    inputs: dict[str, object] = Field(default_factory=dict)


class ConfirmationResult(BaseModel):
    """一次确认操作的结果。"""

    status: ConfirmationResultStatus
    proposal: ConfirmationProposal | None = None
    approved_dispatch: ApprovedCapabilityDispatch | None = None
    message: str
    error_code: str | None = None
