from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_intent_interaction_gateway
from app.main import create_app
from app.platform.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.gateway import (
    ControlledDispatcher,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.platform.interaction.application.intent_recognition import (
    IntentRecognitionCommand,
    StructuredIntentRecognition,
)
from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.llm.contracts import StructuredLlmResult

TENDER_CODE = "tender.generate_bid_skeleton"
TENDER_DISPATCH_KEY = "agent.tender.generate_bid_skeleton"
TENDER_PERMISSION = "agent:tender:execute"


def _tender_capability() -> PlatformCapability:
    return PlatformCapability(
        code=TENDER_CODE,
        capability_type="agent",
        description="Generate a tender bid skeleton.",
        input_schema={
            "type": "object",
            "properties": {
                "file_name": {"type": "string"},
                "content_base64": {"type": "string"},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("file_name", "content_base64"),
        confirmation_policy="always",
        permission=(TENDER_PERMISSION,),
        enabled=True,
        timeout_seconds=120,
        error_boundary="tender-test",
        dispatch_key=TENDER_DISPATCH_KEY,
        retrieval_metadata={
            "aliases": ["tender analysis", "bid skeleton"],
            "examples": ["generate a tender bid skeleton"],
        },
    )


class FakeCatalog:
    def __init__(self, capabilities: tuple[PlatformCapability, ...]) -> None:
        self.capabilities = capabilities
        self.list_calls: list[tuple[str, ...]] = []
        self.get_calls: list[tuple[str, tuple[str, ...]]] = []

    def list_available(self, *, permissions=()):  # noqa: ANN001
        normalized = tuple(sorted({item.strip() for item in permissions if item.strip()}))
        self.list_calls.append(normalized)
        return tuple(
            capability
            for capability in self.capabilities
            if set(capability.permission).issubset(normalized)
        )

    def get_available(self, code: str, *, permissions=()):  # noqa: ANN001
        normalized = tuple(sorted({item.strip() for item in permissions if item.strip()}))
        self.get_calls.append((code, normalized))
        return next(
            (
                capability
                for capability in self.capabilities
                if capability.code == code and set(capability.permission).issubset(normalized)
            ),
            None,
        )


class FakeEmbedding:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_text(self, text: str) -> list[float]:  # noqa: ARG002
        return [1.0, 0.0]


class FakeStructuredLlm:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = []

    def invoke(self, request, output_schema):  # noqa: ANN001
        self.calls.append(request)
        value = output_schema.model_validate(self.payload)
        return StructuredLlmResult(
            value=value,
            model="security-test-model",
            prompt_version=request.prompt_version,
        )


@dataclass
class RecordingAgent:
    calls: list[dict[str, object]]

    def __call__(
        self,
        capability_code: str,
        dispatch_key: str,
        inputs: dict[str, object],
        principal,
    ) -> object:  # noqa: ANN001
        self.calls.append(
            {
                "capability_code": capability_code,
                "dispatch_key": dispatch_key,
                "inputs": dict(inputs),
                "subject": principal.subject,
            }
        )
        return {"ok": True}


def _gateway(
    catalog: FakeCatalog,
    llm: FakeStructuredLlm,
    agent: RecordingAgent,
) -> IntentInteractionGateway:
    retrieval = CapabilityCandidateRetrieval(catalog, FakeEmbedding())
    recognition = StructuredIntentRecognition(retrieval, catalog, llm)
    return IntentInteractionGateway(
        candidate_retrieval=retrieval,
        intent_recognition=recognition,
        confirmation=ExplicitCapabilityConfirmation(catalog),
        proposal_store=InMemoryPendingProposalStore(),
        dispatcher=ControlledDispatcher(catalog, {}, agent_handler=agent),
    )


def test_candidate_and_catalog_visibility_follow_principal_permissions() -> None:
    catalog = FakeCatalog((_tender_capability(),))
    retrieval = CapabilityCandidateRetrieval(catalog, FakeEmbedding())

    anonymous_build = retrieval.refresh()
    anonymous_result = retrieval.search("generate a tender bid skeleton")
    authorized_permissions = (TENDER_PERMISSION,)
    authorized_build = retrieval.refresh(permissions=authorized_permissions)
    authorized_result = retrieval.search(
        "generate a tender bid skeleton",
        permissions=authorized_permissions,
    )

    assert anonymous_build.indexed_count == 0
    assert anonymous_result.status == "empty"
    assert authorized_build.indexed_count == 1
    assert [item.capability_code for item in authorized_result.candidates] == [TENDER_CODE]
    assert catalog.get_available(TENDER_CODE, permissions=()) is None
    assert catalog.get_available(TENDER_CODE, permissions=authorized_permissions) is not None


def test_structured_recognition_rechecks_tender_catalog_with_authorized_principal() -> None:
    catalog = FakeCatalog((_tender_capability(),))
    retrieval = CapabilityCandidateRetrieval(catalog, FakeEmbedding())
    permissions = (TENDER_PERMISSION,)
    retrieval.refresh(permissions=permissions)
    llm = FakeStructuredLlm(
        {
            "status": "matched",
            "capability_code": TENDER_CODE,
            "extracted_inputs": {},
        }
    )
    recognition = StructuredIntentRecognition(retrieval, catalog, llm)

    assessment = recognition.recognize(
        IntentRecognitionCommand(
            "generate a tender bid skeleton",
            permissions=permissions,
            provided_inputs={"file_name": "tender.docx", "content_base64": "AA=="},
        )
    )

    assert assessment.status == "matched"
    assert assessment.capability_code == TENDER_CODE
    assert all(call_permissions == permissions for _, call_permissions in catalog.get_calls)


def test_http_static_principal_enters_tender_candidate_chain(monkeypatch) -> None:  # noqa: ANN001
    from app.shared.config import settings

    monkeypatch.setattr(settings, "request_principal_mode", "static")
    monkeypatch.setattr(settings, "static_principal_subject", "local-operator")
    monkeypatch.setattr(settings, "static_principal_permissions", TENDER_PERMISSION)
    catalog = FakeCatalog((_tender_capability(),))
    llm = FakeStructuredLlm(
        {"status": "matched", "capability_code": TENDER_CODE, "extracted_inputs": {}}
    )
    agent = RecordingAgent(calls=[])
    gateway = _gateway(catalog, llm, agent)
    application = create_app()
    application.dependency_overrides[get_intent_interaction_gateway] = lambda: gateway

    try:
        response = TestClient(application).post(
            "/api/v1/interaction/intent",
            headers={"x-permissions": "forged:admin"},
            json={
                "user_input": "generate a tender bid skeleton",
                "provided_inputs": {"file_name": "tender.docx", "content_base64": "AA=="},
            },
        )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["assessment"]["capability_code"] == TENDER_CODE
    assert catalog.list_calls == [(TENDER_PERMISSION,)]
    assert all(
        call_permissions == (TENDER_PERMISSION,) for _, call_permissions in catalog.get_calls
    )
    assert agent.calls == []


def test_http_static_tender_request_without_file_returns_clarification_without_agent_call(
    monkeypatch,
) -> None:  # noqa: ANN001
    from app.shared.config import settings

    monkeypatch.setattr(settings, "request_principal_mode", "static")
    monkeypatch.setattr(settings, "static_principal_subject", "local-operator")
    monkeypatch.setattr(settings, "static_principal_permissions", TENDER_PERMISSION)
    catalog = FakeCatalog((_tender_capability(),))
    llm = FakeStructuredLlm(
        {"status": "matched", "capability_code": TENDER_CODE, "extracted_inputs": {}}
    )
    agent = RecordingAgent(calls=[])
    gateway = _gateway(catalog, llm, agent)
    application = create_app()
    application.dependency_overrides[get_intent_interaction_gateway] = lambda: gateway

    try:
        response = TestClient(application).post(
            "/api/v1/interaction/intent",
            json={"user_input": "generate a tender bid skeleton", "provided_inputs": {}},
        )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["assessment"]["capability_code"] == TENDER_CODE
    assert set(body["assessment"]["missing_fields"]) == {"file_name", "content_base64"}
    assert agent.calls == []
