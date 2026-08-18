from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.composition.interaction import build_controlled_dispatcher
from app.interfaces.http.dependencies import get_intent_interaction_gateway
from app.main import create_app
from app.modules.agent.runtime import AgentRuntime
from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.gateway import (
    ControlledDispatcher,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.interaction.domain.confirmation import ConfirmationProposal
from app.modules.interaction.domain.intent import IntentAssessment
from app.modules.security.domain.principal import RequestPrincipal


def _capability(
    code: str = "chat.general",
    *,
    capability_type: str = "chat",
    input_schema: dict[str, object] | None = None,
    required_fields: tuple[str, ...] = ("message",),
    permission: tuple[str, ...] = (),
    dispatch_key: str = "llm.chat",
    confirmation_policy: str = "always",
) -> PlatformCapability:
    return PlatformCapability(
        code=code,
        capability_type=capability_type,  # type: ignore[arg-type]
        description="通用对话",
        input_schema=input_schema
        or {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=required_fields,
        confirmation_policy=confirmation_policy,  # type: ignore[arg-type]
        permission=permission,
        enabled=True,
        timeout_seconds=120,
        error_boundary="chat-v1",
        dispatch_key=dispatch_key,
        retrieval_metadata={},
    )


class FakeCatalog:
    def __init__(self, capability: PlatformCapability) -> None:
        self.capability = capability

    def get_available(
        self,
        code: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> PlatformCapability | None:
        if code != self.capability.code:
            return None
        if not set(self.capability.permission).issubset(permissions):
            return None
        return self.capability


class ReadyCandidateRetrieval:
    def is_ready(self, *, permissions: tuple[str, ...] = ()) -> bool:  # noqa: ARG002
        return True

    def refresh(self, *, permissions: tuple[str, ...] = ()):  # noqa: ARG002
        raise AssertionError("ready index must not be refreshed")


class MatchedIntentRecognition:
    def recognize(self, command):  # noqa: ANN001
        return IntentAssessment(
            status="matched",
            capability_code="chat.general",
            extracted_inputs={"message": command.provided_inputs.get("message", "你好")},
        )


class StaticIntentRecognition:
    def __init__(self, assessment: IntentAssessment) -> None:
        self.assessment = assessment

    def recognize(self, command):  # noqa: ANN001, ARG002
        return self.assessment


@dataclass
class RecordingHandler:
    calls: list[dict[str, object]]

    def __call__(self, inputs: dict[str, object]) -> object:
        self.calls.append(inputs)
        return {"answer": "已执行"}


def _gateway(
    *,
    capability: PlatformCapability | None = None,
    store: InMemoryPendingProposalStore | None = None,
    handler: RecordingHandler | None = None,
) -> tuple[IntentInteractionGateway, RecordingHandler]:
    catalog = FakeCatalog(capability or _capability())
    recording_handler = handler or RecordingHandler(calls=[])
    return (
        IntentInteractionGateway(
            candidate_retrieval=ReadyCandidateRetrieval(),  # type: ignore[arg-type]
            intent_recognition=MatchedIntentRecognition(),  # type: ignore[arg-type]
            confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
            proposal_store=store or InMemoryPendingProposalStore(),
            dispatcher=ControlledDispatcher(catalog, {"llm.chat": recording_handler}),
        ),
        recording_handler,
    )


def _principal(
    *,
    subject: str | None = "user-1",
    permissions: frozenset[str] = frozenset(),
) -> RequestPrincipal:
    return RequestPrincipal(
        subject=subject,
        permissions=permissions,
        authenticated=subject is not None,
    )


def test_gateway_requires_confirmation_and_consumes_the_proposal_once() -> None:
    gateway, handler = _gateway()
    principal = _principal()

    recognized = gateway.recognize(
        GatewayRecognitionCommand(
            user_input="帮我回答问题",
            principal=principal,
            provided_inputs={"message": "你好"},
        )
    )

    assert recognized.status == "pending"
    assert recognized.proposal is not None
    assert handler.calls == []

    confirmed = gateway.confirm(
        GatewayConfirmationCommand(
            proposal_id=recognized.proposal.proposal_id,
            action="confirm",
            principal=principal,
        )
    )

    assert confirmed.status == "completed"
    assert confirmed.execution_result == {"answer": "已执行"}
    assert handler.calls == [{"message": "你好"}]

    repeated = gateway.confirm(
        GatewayConfirmationCommand(
            proposal_id=recognized.proposal.proposal_id,
            action="confirm",
            principal=principal,
        )
    )

    assert repeated.status == "rejected"
    assert repeated.error_code == "PROPOSAL_UNAVAILABLE"
    assert handler.calls == [{"message": "你好"}]


def test_gateway_authorizes_catalog_controlled_never_policy_without_proposal() -> None:
    gateway, handler = _gateway(
        capability=_capability(confirmation_policy="never"),
    )

    recognized = gateway.recognize(
        GatewayRecognitionCommand(
            user_input="帮我回答一个问题",
            principal=_principal(),
            provided_inputs={"message": "你好"},
        )
    )

    assert recognized.status == "authorized"
    assert recognized.proposal is None
    assert recognized.direct_execution is not None
    assert recognized.direct_execution.capability_code == "chat.general"
    assert recognized.direct_execution.dispatch_key == "llm.chat"
    assert recognized.direct_execution.inputs == {"message": "你好"}
    assert handler.calls == []


def test_gateway_treats_conditional_policy_as_requiring_confirmation() -> None:
    gateway, handler = _gateway(
        capability=_capability(confirmation_policy="conditional"),
    )

    recognized = gateway.recognize(
        GatewayRecognitionCommand(
            user_input="帮我回答一个问题",
            principal=_principal(),
            provided_inputs={"message": "你好"},
        )
    )

    assert recognized.status == "pending"
    assert recognized.proposal is not None
    assert handler.calls == []


def test_client_supplied_inputs_cannot_change_the_catalog_confirmation_policy() -> None:
    gateway, handler = _gateway()

    recognized = gateway.recognize(
        GatewayRecognitionCommand(
            user_input="帮我回答一个问题",
            principal=_principal(),
            provided_inputs={
                "message": "你好",
                "confirmation_policy": "never",
                "dispatch_key": "agent.tender.generate_bid_skeleton",
            },
        )
    )

    assert recognized.status == "pending"
    assert recognized.proposal is not None
    assert handler.calls == []


def test_gateway_cancellation_consumes_proposal_without_execution() -> None:
    gateway, handler = _gateway()
    principal = _principal()
    recognized = gateway.recognize(
        GatewayRecognitionCommand("取消测试", principal, {"message": "你好"})
    )

    assert recognized.proposal is not None
    cancelled = gateway.confirm(
        GatewayConfirmationCommand(recognized.proposal.proposal_id, "cancel", principal)
    )

    assert cancelled.status == "cancelled"
    assert handler.calls == []


def test_gateway_rejects_protected_capability_for_anonymous_principal() -> None:
    gateway, handler = _gateway(capability=_capability(permission=("agent:tender:execute",)))

    result = gateway.recognize(
        GatewayRecognitionCommand(
            user_input="执行受保护能力",
            principal=RequestPrincipal.anonymous(),
            provided_inputs={"message": "你好"},
        )
    )

    assert result.status == "rejected"
    assert result.error_code == "CAPABILITY_UNAVAILABLE"
    assert handler.calls == []


def test_gateway_binds_proposal_to_subject_without_consuming_on_mismatch() -> None:
    gateway, handler = _gateway()
    owner = _principal(subject="owner")
    recognized = gateway.recognize(
        GatewayRecognitionCommand("主体绑定", owner, {"message": "你好"})
    )

    assert recognized.proposal is not None
    rejected = gateway.confirm(
        GatewayConfirmationCommand(
            recognized.proposal.proposal_id,
            "confirm",
            _principal(subject="other"),
        )
    )
    assert rejected.error_code == "PROPOSAL_UNAVAILABLE"
    assert handler.calls == []

    completed = gateway.confirm(
        GatewayConfirmationCommand(recognized.proposal.proposal_id, "confirm", owner)
    )
    assert completed.status == "completed"
    assert len(handler.calls) == 1


def test_gateway_rejects_expired_proposal_without_execution() -> None:
    clock = [0.0]
    store = InMemoryPendingProposalStore(ttl_seconds=1.0, clock=lambda: clock[0])
    gateway, handler = _gateway(store=store)
    principal = _principal()
    recognized = gateway.recognize(
        GatewayRecognitionCommand("过期确认", principal, {"message": "你好"})
    )

    assert recognized.proposal is not None
    clock[0] = 1.0
    expired = gateway.confirm(
        GatewayConfirmationCommand(recognized.proposal.proposal_id, "confirm", principal)
    )

    assert expired.error_code == "PROPOSAL_UNAVAILABLE"
    assert handler.calls == []


def test_gateway_dispatches_agent_via_runtime_only_after_confirmed_authorization() -> None:
    capability = _capability(
        "agent.tender.generate_bid_skeleton",
        capability_type="agent",
        input_schema={
            "type": "object",
            "properties": {"file_name": {"type": "string"}},
            "additionalProperties": False,
        },
        required_fields=("file_name",),
        permission=("agent:tender:execute",),
        dispatch_key="agent.tender.generate_bid_skeleton",
    )
    catalog = FakeCatalog(capability)
    handler = RecordingHandler(calls=[])
    runtime = AgentRuntime(
        catalog,  # type: ignore[arg-type]
        {capability.dispatch_key: handler},
    )
    gateway = IntentInteractionGateway(
        candidate_retrieval=ReadyCandidateRetrieval(),  # type: ignore[arg-type]
        intent_recognition=StaticIntentRecognition(
            IntentAssessment(
                status="matched",
                capability_code=capability.code,
                extracted_inputs={"file_name": "招标文件.docx"},
            )
        ),  # type: ignore[arg-type]
        confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=ControlledDispatcher(
            catalog,  # type: ignore[arg-type]
            {},
            agent_handler=lambda code, key, inputs, principal: runtime.execute(
                capability_code=code,
                dispatch_key=key,
                inputs=inputs,
                permissions=principal.permission_tuple(),
            ),
        ),
    )
    principal = _principal(permissions=frozenset({"agent:tender:execute"}))

    recognized = gateway.recognize(
        GatewayRecognitionCommand("生成投标骨架", principal, {})
    )

    assert recognized.status == "pending"
    assert recognized.proposal is not None
    assert handler.calls == []

    completed = gateway.confirm(
        GatewayConfirmationCommand(
            recognized.proposal.proposal_id,
            "confirm",
            principal,
        )
    )

    assert completed.status == "completed"
    assert handler.calls == [{"file_name": "招标文件.docx"}]


def test_gateway_returns_clarification_without_creating_or_dispatching_a_proposal() -> None:
    capability = _capability()
    catalog = FakeCatalog(capability)
    handler = RecordingHandler(calls=[])
    gateway = IntentInteractionGateway(
        candidate_retrieval=ReadyCandidateRetrieval(),  # type: ignore[arg-type]
        intent_recognition=StaticIntentRecognition(
            IntentAssessment(
                status="needs_clarification",
                capability_code=capability.code,
                missing_fields=["message"],
                clarification="请补充需要回复的内容。",
                error_code="INPUT_VALIDATION_FAILED",
            )
        ),  # type: ignore[arg-type]
        confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=ControlledDispatcher(catalog, {"llm.chat": handler}),  # type: ignore[arg-type]
    )

    result = gateway.recognize(
        GatewayRecognitionCommand("帮我回复", _principal(), {})
    )

    assert result.status == "needs_clarification"
    assert result.assessment is not None
    assert result.assessment.missing_fields == ["message"]
    assert result.proposal is None
    assert handler.calls == []


def test_gateway_returns_controlled_failure_when_dispatch_execution_fails() -> None:
    catalog = FakeCatalog(_capability())
    calls: list[dict[str, object]] = []

    def fail_execution(inputs: dict[str, object]) -> object:
        calls.append(inputs)
        raise RuntimeError("provider unavailable")

    gateway = IntentInteractionGateway(
        candidate_retrieval=ReadyCandidateRetrieval(),  # type: ignore[arg-type]
        intent_recognition=MatchedIntentRecognition(),  # type: ignore[arg-type]
        confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=ControlledDispatcher(catalog, {"llm.chat": fail_execution}),  # type: ignore[arg-type]
    )
    principal = _principal()
    recognized = gateway.recognize(
        GatewayRecognitionCommand("执行会失败", principal, {"message": "你好"})
    )

    assert recognized.proposal is not None
    result = gateway.confirm(
        GatewayConfirmationCommand(recognized.proposal.proposal_id, "confirm", principal)
    )

    assert result.status == "failed"
    assert result.error_code == "DISPATCH_EXECUTION_FAILED"
    assert calls == [{"message": "你好"}]


def test_gateway_maps_policy_review_inputs_to_decision_review_command() -> None:
    capability = _capability(
        "policy.review",
        capability_type="policy_decision",
        input_schema={
            "type": "object",
            "properties": {
                "scenario_code": {"type": "string"},
                "submitted_materials": {"type": "array"},
                "top_k": {"type": "integer"},
                "document_id": {"type": "integer"},
                "include_history": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        required_fields=("scenario_code", "submitted_materials"),
        dispatch_key="online.policy_decision.review",
    )
    catalog = FakeCatalog(capability)

    class RecordingPolicyApplication:
        def __init__(self) -> None:
            self.commands: list[object] = []

        def review(self, command: object) -> object:
            self.commands.append(command)
            return {"status": "reviewed"}

    policy_application = RecordingPolicyApplication()
    dispatcher = build_controlled_dispatcher(
        catalog,  # type: ignore[arg-type]
        agent_runtime=lambda: (_ for _ in ()).throw(AssertionError("unused")),
        chat_application=lambda: (_ for _ in ()).throw(AssertionError("unused")),
        ask_knowledge_use_case=lambda: (_ for _ in ()).throw(AssertionError("unused")),
        policy_decision_application_service=lambda: policy_application,  # type: ignore[arg-type]
    )
    gateway = IntentInteractionGateway(
        candidate_retrieval=ReadyCandidateRetrieval(),  # type: ignore[arg-type]
        intent_recognition=StaticIntentRecognition(
            IntentAssessment(
                status="matched",
                capability_code=capability.code,
                extracted_inputs={
                    "scenario_code": "court-evaluation-materials",
                    "submitted_materials": ["complaint", "evidence"],
                    "top_k": 6,
                    "document_id": 18,
                    "include_history": True,
                },
            )
        ),  # type: ignore[arg-type]
        confirmation=ExplicitCapabilityConfirmation(catalog),  # type: ignore[arg-type]
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=dispatcher,
    )
    principal = _principal()
    recognized = gateway.recognize(
        GatewayRecognitionCommand("审查材料", principal, {})
    )

    assert recognized.proposal is not None
    result = gateway.confirm(
        GatewayConfirmationCommand(recognized.proposal.proposal_id, "confirm", principal)
    )

    assert result.status == "completed"
    assert len(policy_application.commands) == 1
    command = policy_application.commands[0]
    assert command.scenario_code == "court-evaluation-materials"  # type: ignore[union-attr]
    assert command.submitted_materials == ("complaint", "evidence")  # type: ignore[union-attr]
    assert command.top_k == 6  # type: ignore[union-attr]
    assert command.document_id == 18  # type: ignore[union-attr]
    assert command.include_history is True  # type: ignore[union-attr]


def test_http_gateway_uses_anonymous_principal_not_forged_permission_header() -> None:
    class RecordingGateway:
        principal: RequestPrincipal | None = None

        def recognize(self, command: GatewayRecognitionCommand) -> GatewayResult:
            self.principal = command.principal
            return GatewayResult(
                status="needs_clarification",
                message="需要补充信息。",
            )

    gateway = RecordingGateway()
    application = create_app()
    application.dependency_overrides[get_intent_interaction_gateway] = lambda: gateway
    response = TestClient(application).post(
        "/api/v1/interaction/intent",
        headers={"x-permissions": "agent:tender:execute"},
        json={"user_input": "执行 Agent", "provided_inputs": {}},
    )

    assert response.status_code == 200
    assert gateway.principal == RequestPrincipal.anonymous()
    application.dependency_overrides.clear()


def test_http_gateway_does_not_expose_dispatch_key_or_complete_inputs() -> None:
    class PendingGateway:
        def recognize(self, command: GatewayRecognitionCommand) -> GatewayResult:  # noqa: ARG002
            return GatewayResult(
                status="pending",
                message="等待确认。",
                assessment=IntentAssessment(
                    status="matched",
                    capability_code="chat.general",
                    extracted_inputs={"content_base64": "sensitive-content"},
                    candidate_codes=["chat.general", "other.internal"],
                    model="internal-model",
                    prompt_version="internal-prompt",
                ),
                proposal=ConfirmationProposal(
                    proposal_id="proposal-1",
                    capability_code="chat.general",
                    dispatch_key="llm.chat",
                    inputs={"message": "不应回传的完整输入"},
                    summary="通用对话",
                    confirmation_prompt="确认执行吗？",
                ),
            )

    application = create_app()
    application.dependency_overrides[get_intent_interaction_gateway] = PendingGateway
    response = TestClient(application).post(
        "/api/v1/interaction/intent",
        json={"user_input": "聊天", "provided_inputs": {}},
    )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["proposal_id"] == "proposal-1"
    assert "dispatch_key" not in proposal
    assert "inputs" not in proposal
    assessment = response.json()["assessment"]
    assert assessment["capability_code"] == "chat.general"
    assert "extracted_inputs" not in assessment
    assert "candidate_codes" not in assessment
    assert "model" not in assessment
    assert "prompt_version" not in assessment
    application.dependency_overrides.clear()


def test_http_confirmation_returns_cancelled_and_failed_states() -> None:
    class ControlledGateway:
        def confirm(self, command: GatewayConfirmationCommand) -> GatewayResult:
            if command.action == "cancel":
                return GatewayResult(status="cancelled", message="已取消。")
            return GatewayResult(
                status="failed",
                message="目标能力执行失败。",
                error_code="DISPATCH_EXECUTION_FAILED",
            )

    application = create_app()
    application.dependency_overrides[get_intent_interaction_gateway] = ControlledGateway
    client = TestClient(application)

    cancelled = client.post(
        "/api/v1/interaction/proposals/proposal-1/confirmation",
        json={"action": "cancel"},
    )
    failed = client.post(
        "/api/v1/interaction/proposals/proposal-2/confirmation",
        json={"action": "confirm"},
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_code"] == "DISPATCH_EXECUTION_FAILED"
    application.dependency_overrides.clear()
