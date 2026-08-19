from __future__ import annotations

from collections.abc import Callable, Iterable
from uuid import uuid4

from app.modules.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
    ConfirmationResult,
)
from app.modules.interaction.domain.intent import IntentAssessment, validate_capability_inputs
from app.modules.interaction.ports.capability_catalog import CapabilityCatalogPort

_CONFIRM_WORDS = frozenset(
    {"confirm", "yes", "y", "ok", "approve", "\u786e\u8ba4", "\u540c\u610f"}
)
_CANCEL_WORDS = frozenset(
    {"cancel", "no", "n", "reject", "\u53d6\u6d88", "\u4e0d\u786e\u8ba4", "\u62d2\u7edd"}
)


class ExplicitCapabilityConfirmation:
    """Manage an in-request confirmation proposal without executing it."""

    def __init__(
        self,
        capability_catalog: CapabilityCatalogPort,
        *,
        proposal_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._capability_catalog = capability_catalog
        self._proposal_id_factory = proposal_id_factory or _new_proposal_id

    @property
    def capability_catalog(self) -> CapabilityCatalogPort:
        """Expose the catalog only to the interaction application boundary."""

        return self._capability_catalog

    def create_proposal(
        self,
        assessment: IntentAssessment,
        *,
        permissions: Iterable[str] = (),
    ) -> ConfirmationResult:
        if assessment.status != "matched" or assessment.capability_code is None:
            return _rejected(
                "当前没有可确认的有效请求。",
                "NO_MATCHED_INTENT",
            )

        normalized_permissions = tuple(
            permission.strip() for permission in permissions if permission.strip()
        )
        try:
            capability = self._capability_catalog.get_available(
                assessment.capability_code,
                permissions=normalized_permissions,
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return _rejected(
                "当前服务暂时不可用，请稍后重试。",
                "CAPABILITY_CATALOG_UNAVAILABLE",
            )

        if capability is None:
            return _rejected(
                "当前请求暂时无法处理。",
                "CAPABILITY_UNAVAILABLE",
            )
        if capability.confirmation_policy == "never":
            return _rejected(
                "当前能力不需要确认，不能创建待确认提议。",
                "CONFIRMATION_NOT_REQUIRED",
            )

        validation = validate_capability_inputs(capability, assessment.extracted_inputs)
        if not validation.valid:
            return _rejected(
                "当前请求的信息还不完整，暂时无法提交批准。",
                "INPUT_VALIDATION_FAILED",
            )

        proposal = ConfirmationProposal(
            proposal_id=self._proposal_id_factory(),
            capability_code=capability.code,
            capability_type=capability.capability_type,
            dispatch_key=capability.dispatch_key,
            inputs=dict(assessment.extracted_inputs),
            summary=capability.description,
            confirmation_prompt="批准后将开始处理该请求。",
        )
        return ConfirmationResult(
            status="pending",
            proposal=proposal,
            message="需要你的明确批准后才会开始处理。",
        )

    def respond(
        self,
        proposal: ConfirmationProposal,
        confirmation_input: str | None,
    ) -> ConfirmationResult:
        if proposal.state == "cancelled":
            return _rejected("该请求已经取消。", "PROPOSAL_CANCELLED")
        if proposal.state != "pending":
            return _rejected(
                "该请求不再等待批准。",
                "PROPOSAL_NOT_PENDING",
            )

        normalized_input = (confirmation_input or "").strip().lower()
        if not normalized_input:
            return ConfirmationResult(
                status="pending",
                proposal=proposal,
                message="请明确选择批准执行或取消。",
            )
        if normalized_input in _CANCEL_WORDS:
            cancelled = proposal.model_copy(update={"state": "cancelled"})
            return ConfirmationResult(
                status="cancelled",
                proposal=cancelled,
                message="已取消该请求，未执行任何操作。",
            )
        if normalized_input not in _CONFIRM_WORDS:
            return ConfirmationResult(
                status="pending",
                proposal=proposal,
                message="请明确选择批准执行或取消。",
                error_code="UNRECOGNIZED_CONFIRMATION_INPUT",
            )

        confirmed = proposal.model_copy(update={"state": "confirmed"})
        return ConfirmationResult(
            status="confirmed",
            proposal=confirmed,
            approved_dispatch=ApprovedCapabilityDispatch(
                proposal_id=confirmed.proposal_id,
                capability_code=confirmed.capability_code,
                dispatch_key=confirmed.dispatch_key,
                inputs=dict(confirmed.inputs),
            ),
            message="请求已获批准。",
        )


def _new_proposal_id() -> str:
    return uuid4().hex


def _rejected(message: str, error_code: str) -> ConfirmationResult:
    return ConfirmationResult(status="rejected", message=message, error_code=error_code)
