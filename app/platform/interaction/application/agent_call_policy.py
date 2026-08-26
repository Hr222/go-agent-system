"""结构化 Agent Call 的目录、输入与确认策略校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.platform.interaction.domain.agent_call import StructuredAgentCall
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.interaction.domain.confirmation import ApprovedCapabilityDispatch
from app.platform.interaction.domain.intent import validate_capability_inputs
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.security.domain.principal import RequestPrincipal

AgentCallPolicyStatus = Literal[
    "authorized",
    "confirmation_required",
    "rejected",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class AgentCallPolicyCommand:
    """策略校验的内部输入；批准对象只能来自确认应用边界。"""

    call: StructuredAgentCall
    principal: RequestPrincipal
    approved_dispatch: ApprovedCapabilityDispatch | None = None


@dataclass(frozen=True, slots=True)
class AgentCallPolicyResult:
    """不触发执行的 Agent Call 策略结果。"""

    status: AgentCallPolicyStatus
    message: str
    call: StructuredAgentCall
    error_code: str | None = None


class AgentCallPolicyValidator:
    """按平台目录确定性校验结构化 Agent Call。"""

    def __init__(self, capability_catalog: CapabilityCatalogPort) -> None:
        self._capability_catalog = capability_catalog

    def validate(self, command: AgentCallPolicyCommand) -> AgentCallPolicyResult:
        permissions = command.principal.permission_tuple()
        try:
            capability = self._capability_catalog.get_available(
                command.call.capability_code,
                permissions=permissions,
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return _result(
                command.call,
                status="unavailable",
                message="能力目录暂时不可用，未授权该 Agent 调用。",
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
            )

        if capability is None:
            return _result(
                command.call,
                status="rejected",
                message="该 Agent 能力当前不可用或当前主体没有调用权限。",
                error_code="CAPABILITY_UNAVAILABLE",
            )
        if capability.capability_type != "agent":
            return _result(
                command.call,
                status="rejected",
                message="结构化调用目标不是可调用的 Agent 能力。",
                error_code="CAPABILITY_TYPE_NOT_AGENT",
            )

        input_validation = validate_capability_inputs(capability, command.call.inputs)
        if not input_validation.valid:
            return _result(
                command.call,
                status="rejected",
                message="Agent 调用输入不符合当前能力契约。",
                error_code="INPUT_VALIDATION_FAILED",
            )

        if command.approved_dispatch is not None and not _approval_matches(
            command.call,
            capability,
            command.approved_dispatch,
        ):
            return _result(
                command.call,
                status="rejected",
                message="确认提议与当前 Agent 调用不一致，未授权执行。",
                error_code="APPROVAL_MISMATCH",
            )

        if capability.confirmation_policy == "never":
            return _result(
                command.call,
                status="authorized",
                message="Agent 调用已通过服务端策略校验。",
            )
        if command.approved_dispatch is None:
            return _result(
                command.call,
                status="confirmation_required",
                message="该 Agent 调用需要用户明确确认。",
                error_code="CONFIRMATION_REQUIRED",
            )
        return _result(
            command.call,
            status="authorized",
            message="Agent 调用已通过确认和服务端策略校验。",
        )


def _approval_matches(
    call: StructuredAgentCall,
    capability: PlatformCapability,
    approved_dispatch: ApprovedCapabilityDispatch,
) -> bool:
    return (
        approved_dispatch.capability_code == call.capability_code
        and approved_dispatch.capability_code == capability.code
        and approved_dispatch.dispatch_key == capability.dispatch_key
        and dict(approved_dispatch.inputs) == dict(call.inputs)
    )


def _result(
    call: StructuredAgentCall,
    *,
    status: AgentCallPolicyStatus,
    message: str,
    error_code: str | None = None,
) -> AgentCallPolicyResult:
    return AgentCallPolicyResult(
        status=status,
        message=message,
        call=call.model_copy(deep=True),
        error_code=error_code,
    )


__all__ = [
    "AgentCallPolicyCommand",
    "AgentCallPolicyResult",
    "AgentCallPolicyStatus",
    "AgentCallPolicyValidator",
]
