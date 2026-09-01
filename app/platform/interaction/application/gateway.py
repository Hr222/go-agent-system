from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID

from app.platform.attachment import AttachmentAccessContext
from app.platform.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.intent_recognition import (
    IntentRecognitionCommand,
    StructuredIntentRecognition,
)
from app.platform.interaction.domain.attachment import attachment_field_declarations
from app.platform.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
)
from app.platform.interaction.domain.intent import IntentAssessment, validate_capability_inputs
from app.platform.interaction.ports.attachment_resolver import CapabilityAttachmentResolverPort
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.interaction.ports.proposal_store import PendingProposalStorePort
from app.platform.security.domain.principal import RequestPrincipal

GatewayStatus = Literal[
    "needs_clarification",
    "unrecognized",
    "authorized",
    "pending",
    "cancelled",
    "completed",
    "rejected",
    "failed",
]
ConfirmationAction = Literal["confirm", "cancel"]
DialogueConfirmationStatus = Literal["confirmed", "cancelled", "rejected"]
DispatchHandler = Callable[[dict[str, object]], object]
AgentDispatchHandler = Callable[[str, str, dict[str, object], RequestPrincipal], object]

_GENERAL_CHAT_CAPABILITY_CODE = "chat.general"
_GENERAL_CHAT_DISPATCH_KEY = "llm.chat"


@dataclass(frozen=True, slots=True)
class GatewayRecognitionCommand:
    user_input: str
    principal: RequestPrincipal
    provided_inputs: dict[str, object]
    conversation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GatewayConfirmationCommand:
    proposal_id: str
    action: ConfirmationAction
    principal: RequestPrincipal


@dataclass(frozen=True, slots=True)
class GatewayResult:
    status: GatewayStatus
    message: str
    assessment: IntentAssessment | None = None
    proposal: ConfirmationProposal | None = None
    execution_result: object | None = None
    error_code: str | None = None
    direct_execution: "DirectCapabilityExecution | None" = None
    conversation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DialogueAgentConfirmationResult:
    """Chat Agent 确认的内部结果；确认成功时只携带批准分发对象。"""

    status: DialogueConfirmationStatus
    message: str
    proposal: ConfirmationProposal | None = None
    approved_dispatch: ApprovedCapabilityDispatch | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class DirectCapabilityExecution:
    """A server-only, revalidated request allowed to bypass confirmation.

    This value deliberately never crosses the HTTP response boundary.  It carries
    the fixed catalog identity and normalized inputs that a dedicated application
    flow may consume after the `never` policy has been checked.
    """

    capability_code: str
    dispatch_key: str
    inputs: dict[str, object]


@dataclass(frozen=True, slots=True)
class DispatchResult:
    status: Literal["completed", "rejected", "failed"]
    message: str
    execution_result: object | None = None
    error_code: str | None = None


class InMemoryPendingProposalStore(PendingProposalStorePort):
    """进程内短期提议状态，按主体绑定并在读取时原子消费。"""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("确认提议 TTL 必须大于零。")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[ConfirmationProposal, str | None, float]] = {}
        self._lock = Lock()

    def save(self, proposal: ConfirmationProposal, *, subject: str | None) -> None:
        with self._lock:
            self._purge_expired()
            self._entries[proposal.proposal_id] = (
                proposal.model_copy(deep=True),
                subject,
                self._clock() + self._ttl_seconds,
            )

    def consume(
        self,
        proposal_id: str,
        *,
        subject: str | None,
    ) -> ConfirmationProposal | None:
        with self._lock:
            self._purge_expired()
            entry = self._entries.get(proposal_id)
            if entry is None:
                return None
            proposal, proposal_subject, _expires_at = entry
            if proposal_subject != subject:
                return None
            del self._entries[proposal_id]
            return proposal.model_copy(deep=True)

    def _purge_expired(self) -> None:
        now = self._clock()
        expired_ids = [
            proposal_id
            for proposal_id, (_proposal, _subject, expires_at) in self._entries.items()
            if expires_at <= now
        ]
        for proposal_id in expired_ids:
            del self._entries[proposal_id]


class ControlledDispatcher:
    """在确认后按目录重检和固定映射执行已知 Application Use Case。"""

    def __init__(
        self,
        capability_catalog: CapabilityCatalogPort,
        handlers: Mapping[str, DispatchHandler],
        agent_handler: AgentDispatchHandler | None = None,
    ) -> None:
        self._capability_catalog = capability_catalog
        self._handlers = dict(handlers)
        self._agent_handler = agent_handler

    def dispatch(
        self,
        approved: ApprovedCapabilityDispatch,
        *,
        principal: RequestPrincipal,
    ) -> DispatchResult:
        permissions = principal.permission_tuple()
        try:
            capability = self._capability_catalog.get_available(
                approved.capability_code,
                permissions=permissions,
            )
        except Exception:  # noqa: BLE001 - directory failure is an availability boundary
            return DispatchResult(
                status="failed",
                message="能力目录暂时不可用，未执行目标能力。",
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
            )
        if capability is None:
            return DispatchResult(
                status="rejected",
                message="该能力当前不可用或当前主体没有调用权限。",
                error_code="CAPABILITY_UNAVAILABLE",
            )
        if capability.dispatch_key != approved.dispatch_key:
            return DispatchResult(
                status="rejected",
                message="确认提议与当前能力目录不一致，未执行目标能力。",
                error_code="DISPATCH_KEY_MISMATCH",
            )
        validation = validate_capability_inputs(capability, approved.inputs)
        if not validation.valid:
            return DispatchResult(
                status="rejected",
                message="确认提议输入已不符合当前能力契约，未执行目标能力。",
                error_code="DISPATCH_INPUT_INVALID",
            )
        try:
            if capability.capability_type == "agent":
                if self._agent_handler is None:
                    return DispatchResult(
                        status="failed",
                        message="Agent 运行时未配置，未执行目标能力。",
                        error_code="DISPATCH_TARGET_UNAVAILABLE",
                    )
                execution_result = self._agent_handler(
                    capability.code,
                    capability.dispatch_key,
                    dict(approved.inputs),
                    principal,
                )
            else:
                handler = self._handlers.get(capability.dispatch_key)
                if handler is None:
                    return DispatchResult(
                        status="failed",
                        message="能力分发目标未配置，未执行目标能力。",
                        error_code="DISPATCH_TARGET_UNAVAILABLE",
                    )
                execution_result = handler(dict(approved.inputs))
        except LookupError:
            return DispatchResult(
                status="failed",
                message="能力分发目标当前不可用，未执行目标能力。",
                error_code="DISPATCH_TARGET_UNAVAILABLE",
            )
        except ValueError:
            return DispatchResult(
                status="rejected",
                message="能力输入无法构造目标命令，未执行目标能力。",
                error_code="DISPATCH_INPUT_INVALID",
            )
        except Exception:  # noqa: BLE001 - never expose provider or application internals
            return DispatchResult(
                status="failed",
                message="目标能力执行失败。",
                error_code="DISPATCH_EXECUTION_FAILED",
            )
        return DispatchResult(
            status="completed",
            message="目标能力已完成执行。",
            execution_result=execution_result,
        )


class IntentInteractionGateway:
    """将识别、显式确认和受控分发组合为独立应用入口。"""

    def __init__(
        self,
        *,
        candidate_retrieval: CapabilityCandidateRetrieval,
        intent_recognition: StructuredIntentRecognition,
        confirmation: ExplicitCapabilityConfirmation,
        proposal_store: PendingProposalStorePort,
        dispatcher: ControlledDispatcher,
        attachment_resolver: CapabilityAttachmentResolverPort | None = None,
    ) -> None:
        self._candidate_retrieval = candidate_retrieval
        self._intent_recognition = intent_recognition
        self._confirmation = confirmation
        self._proposal_store = proposal_store
        self._dispatcher = dispatcher
        self._attachment_resolver = attachment_resolver

    def recognize(self, command: GatewayRecognitionCommand) -> GatewayResult:
        permissions = command.principal.permission_tuple()
        ensure_ready = getattr(self._candidate_retrieval, "ensure_ready", None)
        if ensure_ready is not None:
            index_result = ensure_ready(permissions=permissions)
            if index_result.status == "failed":
                return GatewayResult(
                    status="needs_clarification",
                    message="能力候选暂时不可用，请稍后重试。",
                    error_code=index_result.error_code or "INDEX_BUILD_FAILED",
                )

        assessment = self._intent_recognition.recognize(
            IntentRecognitionCommand(
                user_input=command.user_input,
                permissions=permissions,
                provided_inputs=dict(command.provided_inputs),
            )
        )
        if assessment.status == "unrecognized":
            fallback = self._prepare_general_chat_fallback(
                command=command,
                assessment=assessment,
                permissions=permissions,
            )
            if fallback is not None:
                return fallback
        if assessment.status != "matched":
            return GatewayResult(
                status=assessment.status,
                message=assessment.clarification or "暂时无法形成可确认的能力提议。",
                assessment=assessment,
                error_code=assessment.error_code,
            )

        attachment_resolution = self._resolve_attachments(assessment, command)
        if isinstance(attachment_resolution, GatewayResult):
            return attachment_resolution
        assessment = attachment_resolution

        direct_execution = self._prepare_unconfirmed_execution(
            assessment,
            permissions=permissions,
        )
        if isinstance(direct_execution, GatewayResult):
            return direct_execution
        if direct_execution is not None:
            return GatewayResult(
                status="authorized",
                message="该请求已通过服务端复核，可以在受控路径中继续处理。",
                assessment=assessment,
                direct_execution=direct_execution,
            )

        confirmation = self._confirmation.create_proposal(
            assessment,
            permissions=permissions,
        )
        if confirmation.status != "pending" or confirmation.proposal is None:
            return GatewayResult(
                status="rejected",
                message=confirmation.message,
                assessment=assessment,
                error_code=confirmation.error_code,
            )
        self._proposal_store.save(
            confirmation.proposal,
            subject=command.principal.subject,
        )
        return GatewayResult(
            status="pending",
            message="已生成待确认提议，明确确认后才会执行。",
            assessment=assessment,
            proposal=confirmation.proposal,
        )

    def _prepare_general_chat_fallback(
        self,
        *,
        command: GatewayRecognitionCommand,
        assessment: IntentAssessment,
        permissions: tuple[str, ...],
    ) -> GatewayResult | None:
        """只为未识别文本回退到目录复核后的通用 Chat。"""

        fallback_assessment = IntentAssessment(
            status="matched",
            capability_code=_GENERAL_CHAT_CAPABILITY_CODE,
            extracted_inputs={"message": command.user_input.strip()},
            candidate_codes=list(assessment.candidate_codes),
        )
        direct_execution = self._prepare_unconfirmed_execution(
            fallback_assessment,
            permissions=permissions,
        )
        if isinstance(direct_execution, GatewayResult) or direct_execution is None:
            return None
        if (
            direct_execution.capability_code != _GENERAL_CHAT_CAPABILITY_CODE
            or direct_execution.dispatch_key != _GENERAL_CHAT_DISPATCH_KEY
        ):
            return None

        return GatewayResult(
            status="authorized",
            message="未识别文本已通过受控通用对话路径复核。",
            assessment=fallback_assessment,
            direct_execution=direct_execution,
        )

    def _resolve_attachments(
        self,
        assessment: IntentAssessment,
        command: GatewayRecognitionCommand,
    ) -> IntentAssessment | GatewayResult:
        if assessment.capability_code is None:
            return GatewayResult(
                status="rejected",
                message="当前请求没有可执行的能力标识。",
                assessment=assessment,
                error_code="MISSING_CAPABILITY_CODE",
            )
        permissions = command.principal.permission_tuple()
        try:
            capability = self._confirmation.capability_catalog.get_available(
                assessment.capability_code,
                permissions=permissions,
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return GatewayResult(
                status="needs_clarification",
                message="能力目录暂时不可用，请稍后重试。",
                assessment=assessment,
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
            )
        if capability is None:
            return GatewayResult(
                status="rejected",
                message="该能力当前不可用或当前主体没有调用权限。",
                assessment=assessment,
                error_code="CAPABILITY_UNAVAILABLE",
            )
        if not attachment_field_declarations(capability.input_schema):
            return assessment
        if self._attachment_resolver is None:
            return GatewayResult(
                status="needs_clarification",
                message="附件解析服务暂时不可用，请稍后重试。",
                assessment=assessment,
                error_code="ATTACHMENT_RESOLUTION_UNAVAILABLE",
            )

        resolution = self._attachment_resolver.resolve(
            capability=capability,
            inputs=dict(assessment.extracted_inputs),
            access_context=AttachmentAccessContext(
                subject=command.principal.subject,
                conversation_id=(
                    str(command.conversation_id)
                    if command.conversation_id is not None
                    else None
                ),
            ),
        )
        if resolution.status != "resolved":
            return GatewayResult(
                status="needs_clarification",
                message="附件无法用于当前请求，请重新上传或检查附件约束。",
                assessment=assessment.model_copy(
                    update={
                        "status": "needs_clarification",
                        "clarification": "请提供满足当前能力约束的附件。",
                        "error_code": resolution.error_code,
                    }
                ),
                error_code=resolution.error_code or "ATTACHMENT_RESOLUTION_FAILED",
            )
        return assessment.model_copy(update={"extracted_inputs": resolution.inputs})

    def _prepare_unconfirmed_execution(
        self,
        assessment: IntentAssessment,
        *,
        permissions: tuple[str, ...],
    ) -> DirectCapabilityExecution | GatewayResult | None:
        """Resolve only catalog-authorized `never` requests.

        Intent output is not execution authority.  The matched capability is read
        again from the server catalog and its input contract is checked before the
        request can enter an approval-free, dedicated execution flow.
        """

        if assessment.capability_code is None:
            return GatewayResult(
                status="rejected",
                message="当前请求没有可执行的能力标识。",
                assessment=assessment,
                error_code="MISSING_CAPABILITY_CODE",
            )
        try:
            capability = self._confirmation.capability_catalog.get_available(
                assessment.capability_code,
                permissions=permissions,
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return GatewayResult(
                status="rejected",
                message="能力目录暂时不可用，未执行目标能力。",
                assessment=assessment,
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
            )
        if capability is None:
            return GatewayResult(
                status="rejected",
                message="该能力当前不可用或当前主体没有调用权限。",
                assessment=assessment,
                error_code="CAPABILITY_UNAVAILABLE",
            )
        if capability.confirmation_policy != "never":
            return None

        validation = validate_capability_inputs(capability, assessment.extracted_inputs)
        if not validation.valid:
            return GatewayResult(
                status="rejected",
                message="请求输入不符合当前能力契约，未执行目标能力。",
                assessment=assessment,
                error_code="INPUT_VALIDATION_FAILED",
            )
        return DirectCapabilityExecution(
            capability_code=capability.code,
            dispatch_key=capability.dispatch_key,
            inputs=dict(assessment.extracted_inputs),
        )

    def confirm(self, command: GatewayConfirmationCommand) -> GatewayResult:
        proposal = self._proposal_store.consume(
            command.proposal_id,
            subject=command.principal.subject,
        )
        if proposal is None:
            return GatewayResult(
                status="rejected",
                message="确认提议不存在、已过期、已处理或不属于当前主体。",
                error_code="PROPOSAL_UNAVAILABLE",
            )
        if proposal.capability_type == "agent":
            return GatewayResult(
                status="rejected",
                message="Agent 调用必须在 Chat 对话中确认，未执行目标能力。",
                proposal=proposal,
                error_code="AGENT_DIALOGUE_CONFIRMATION_REQUIRED",
            )

        confirmation = self._confirmation.respond(proposal, command.action)
        if confirmation.status == "cancelled":
            return GatewayResult(
                status="cancelled",
                message=confirmation.message,
                proposal=confirmation.proposal,
            )
        if confirmation.status != "confirmed" or confirmation.approved_dispatch is None:
            return GatewayResult(
                status="rejected",
                message=confirmation.message,
                proposal=confirmation.proposal,
                error_code=confirmation.error_code,
            )

        dispatched = self._dispatcher.dispatch(
            confirmation.approved_dispatch,
            principal=command.principal,
        )
        return GatewayResult(
            status=dispatched.status,
            message=dispatched.message,
            proposal=confirmation.proposal,
            execution_result=dispatched.execution_result,
            error_code=dispatched.error_code,
        )

    def confirm_dialogue_agent(
        self,
        command: GatewayConfirmationCommand,
    ) -> DialogueAgentConfirmationResult:
        """消费 Chat Agent 提议，但把执行责任交给 Dialogue Invocation。"""

        proposal = self._proposal_store.consume(
            command.proposal_id,
            subject=command.principal.subject,
        )
        if proposal is None:
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="确认提议不存在、已过期、已处理或不属于当前主体。",
                error_code="PROPOSAL_UNAVAILABLE",
            )
        if proposal.capability_type != "agent":
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="该提议不是对话 Agent 调用。",
                proposal=proposal,
                error_code="NOT_AGENT_PROPOSAL",
            )

        permissions = command.principal.permission_tuple()
        try:
            capability = self._confirmation.capability_catalog.get_available(
                proposal.capability_code,
                permissions=permissions,
            )
        except Exception:  # noqa: BLE001 - catalog is an availability boundary
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="能力目录暂时不可用，未执行目标能力。",
                proposal=proposal,
                error_code="CAPABILITY_CATALOG_UNAVAILABLE",
            )
        if capability is None or capability.capability_type != "agent":
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="该 Agent 能力当前不可用或当前主体没有调用权限。",
                proposal=proposal,
                error_code="CAPABILITY_UNAVAILABLE",
            )
        if capability.dispatch_key != proposal.dispatch_key:
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="确认提议与当前能力目录不一致，未执行目标能力。",
                proposal=proposal,
                error_code="DISPATCH_KEY_MISMATCH",
            )
        validation = validate_capability_inputs(capability, proposal.inputs)
        if not validation.valid:
            return DialogueAgentConfirmationResult(
                status="rejected",
                message="确认提议输入已不符合当前能力契约，未执行目标能力。",
                proposal=proposal,
                error_code="DISPATCH_INPUT_INVALID",
            )

        confirmation = self._confirmation.respond(proposal, command.action)
        if confirmation.status == "cancelled":
            return DialogueAgentConfirmationResult(
                status="cancelled",
                message=confirmation.message,
                proposal=confirmation.proposal,
            )
        if confirmation.status != "confirmed" or confirmation.approved_dispatch is None:
            return DialogueAgentConfirmationResult(
                status="rejected",
                message=confirmation.message,
                proposal=confirmation.proposal,
                error_code=confirmation.error_code,
            )
        return DialogueAgentConfirmationResult(
            status="confirmed",
            message=confirmation.message,
            proposal=confirmation.proposal,
            approved_dispatch=confirmation.approved_dispatch,
        )
