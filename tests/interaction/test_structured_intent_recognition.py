from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.composition.root import ApplicationContainer
from app.modules.interaction.application.intent_recognition import (
    IntentRecognitionCommand,
    StructuredIntentRecognition,
)
from app.modules.interaction.domain.candidate import (
    CapabilityCandidate,
    CapabilityCandidateRetrievalResult,
)
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.llm.contracts import StructuredLlmResult


def _capability(
    code: str = "chat.create",
    *,
    enabled: bool = True,
    permission: tuple[str, ...] = (),
) -> PlatformCapability:
    return PlatformCapability(
        code=code,
        capability_type="chat",
        description="Create a chat response.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        required_fields=("message",),
        confirmation_policy="always",
        permission=permission,
        enabled=enabled,
        timeout_seconds=120,
        error_boundary="intent-test",
        dispatch_key="llm.chat",
        retrieval_metadata={},
    )


def _retrieval_result(
    *codes: str,
    status: str = "ready",
) -> CapabilityCandidateRetrievalResult:
    return CapabilityCandidateRetrievalResult(
        query="create a message",
        status=status,  # type: ignore[arg-type]
        candidates=tuple(
            CapabilityCandidate(capability_code=code, score=1.0) for code in codes
        ),
        error_code="INDEX_UNAVAILABLE" if status == "unavailable" else None,
    )


class FakeCandidateRetrieval:
    def __init__(self, result: CapabilityCandidateRetrievalResult) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def search(
        self,
        query: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> CapabilityCandidateRetrievalResult:
        self.calls.append((query, permissions))
        return self.result


class FakeCatalog:
    def __init__(
        self,
        capabilities: tuple[PlatformCapability, ...],
        *,
        disable_after_first_lookup: bool = False,
    ) -> None:
        self.capabilities = {capability.code: capability for capability in capabilities}
        self.disable_after_first_lookup = disable_after_first_lookup
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def get_available(
        self,
        code: str,
        *,
        permissions: tuple[str, ...] = (),
    ) -> PlatformCapability | None:
        self.calls.append((code, permissions))
        capability = self.capabilities.get(code)
        lookup_count = sum(item_code == code for item_code, _ in self.calls)
        if capability is None or not capability.enabled:
            return None
        if self.disable_after_first_lookup and lookup_count > 1:
            return None
        if not set(capability.permission).issubset(permissions):
            return None
        return capability


class FakeStructuredLlm:
    def __init__(self, payload: dict[str, object] | BaseModel) -> None:
        self.payload = payload
        self.calls: list[tuple[object, type[BaseModel]]] = []

    def invoke(self, request, output_schema):  # noqa: ANN001, ANN201
        self.calls.append((request, output_schema))
        value = (
            self.payload
            if isinstance(self.payload, BaseModel)
            else output_schema.model_validate(self.payload)
        )
        return StructuredLlmResult(
            value=value,
            model="test-intent-model",
            prompt_version=request.prompt_version,
        )


class UnboundedIntentOutput(BaseModel):
    status: str
    capability_code: str | None = None
    extracted_inputs: dict[str, object] = {}
    missing_fields: list[str] = []
    clarification: str | None = None
    confidence: float | None = None


def _service(
    payload: dict[str, object] | BaseModel,
    *,
    capability: PlatformCapability | None = None,
    retrieval: CapabilityCandidateRetrievalResult | None = None,
    catalog: FakeCatalog | None = None,
) -> tuple[StructuredIntentRecognition, FakeStructuredLlm, FakeCatalog]:
    selected_capability = capability or _capability()
    selected_catalog = catalog or FakeCatalog((selected_capability,))
    selected_retrieval = retrieval or _retrieval_result(selected_capability.code)
    llm = FakeStructuredLlm(payload)
    service = StructuredIntentRecognition(  # type: ignore[arg-type]
        FakeCandidateRetrieval(selected_retrieval),
        selected_catalog,
        llm,
    )
    return service, llm, selected_catalog


def test_recognition_binds_structured_output_to_retrieved_candidates() -> None:
    service, llm, _ = _service(
        {
            "status": "matched",
            "capability_code": "chat.create",
            "extracted_inputs": {"message": "hello"},
            "confidence": 0.92,
        }
    )

    assessment = service.recognize(IntentRecognitionCommand("create a message"))

    assert assessment.status == "matched"
    assert assessment.capability_code == "chat.create"
    assert assessment.extracted_inputs == {"message": "hello"}
    assert assessment.candidate_codes == ["chat.create"]
    assert assessment.model == "test-intent-model"
    assert assessment.prompt_version == "intent-recognition-v1"
    assert len(llm.calls) == 1
    output_schema = llm.calls[0][1]
    with pytest.raises(ValidationError):
        output_schema.model_validate(
            {
                "status": "matched",
                "capability_code": "outside.catalog",
                "extracted_inputs": {"message": "hello"},
            }
        )


def test_out_of_scope_and_missing_model_capability_codes_do_not_match() -> None:
    out_of_scope_service, out_of_scope_llm, _ = _service(
        UnboundedIntentOutput(
            status="matched",
            capability_code="outside.catalog",
            extracted_inputs={"message": "hello"},
        )
    )
    missing_code_service, _, _ = _service(
        {
            "status": "matched",
            "extracted_inputs": {"message": "hello"},
        }
    )

    out_of_scope = out_of_scope_service.recognize(IntentRecognitionCommand("create a message"))
    missing_code = missing_code_service.recognize(IntentRecognitionCommand("create a message"))

    assert out_of_scope.status == "unrecognized"
    assert out_of_scope.error_code == "INVALID_INTENT_MODEL_RESULT"
    assert missing_code.status == "unrecognized"
    assert missing_code.error_code == "MISSING_CAPABILITY_CODE"
    assert len(out_of_scope_llm.calls) == 1


def test_empty_or_unavailable_candidates_do_not_call_the_llm() -> None:
    empty_service, empty_llm, _ = _service(
        {},
        retrieval=_retrieval_result(status="empty"),
    )
    unavailable_service, unavailable_llm, _ = _service(
        {},
        retrieval=_retrieval_result(status="unavailable"),
    )

    empty = empty_service.recognize(IntentRecognitionCommand("create a message"))
    unavailable = unavailable_service.recognize(IntentRecognitionCommand("create a message"))

    assert empty.status == "unrecognized"
    assert empty.error_code == "NO_CAPABILITY_CANDIDATES"
    assert unavailable.status == "needs_clarification"
    assert unavailable.error_code == "INDEX_UNAVAILABLE"
    assert empty_llm.calls == []
    assert unavailable_llm.calls == []


def test_disabled_or_unauthorized_capability_never_reaches_a_match() -> None:
    disabled_catalog = FakeCatalog((_capability(),), disable_after_first_lookup=True)
    disabled_service, disabled_llm, _ = _service(
        {
            "status": "matched",
            "capability_code": "chat.create",
            "extracted_inputs": {"message": "hello"},
        },
        catalog=disabled_catalog,
    )
    private_capability = _capability(permission=("chat:write",))
    unauthorized_service, unauthorized_llm, _ = _service(
        {},
        capability=private_capability,
    )

    disabled = disabled_service.recognize(IntentRecognitionCommand("create a message"))
    unauthorized = unauthorized_service.recognize(IntentRecognitionCommand("create a message"))

    assert disabled.status == "needs_clarification"
    assert disabled.error_code == "CAPABILITY_UNAVAILABLE"
    assert len(disabled_llm.calls) == 1
    assert unauthorized.status == "needs_clarification"
    assert unauthorized.error_code == "NO_AVAILABLE_CAPABILITY_CANDIDATES"
    assert unauthorized_llm.calls == []


def test_missing_unknown_or_invalid_inputs_require_clarification() -> None:
    missing_service, _, _ = _service(
        {
            "status": "matched",
            "capability_code": "chat.create",
            "extracted_inputs": {},
            "missing_fields": ["message", "model-invented"],
        }
    )
    invalid_service, _, _ = _service(
        {
            "status": "matched",
            "capability_code": "chat.create",
            "extracted_inputs": {"message": 12, "unused": True},
        }
    )

    missing = missing_service.recognize(IntentRecognitionCommand("create a message"))
    invalid = invalid_service.recognize(IntentRecognitionCommand("create a message"))

    assert missing.status == "needs_clarification"
    assert missing.missing_fields == ["message"]
    assert missing.error_code == "INPUT_VALIDATION_FAILED"
    assert invalid.status == "needs_clarification"
    assert invalid.error_code == "INPUT_VALIDATION_FAILED"
    assert invalid.clarification == "请补充完成这项请求所需的信息。"


def test_empty_input_is_resolved_without_retrieval_or_llm() -> None:
    service, llm, _ = _service({})

    assessment = service.recognize(IntentRecognitionCommand("   "))

    assert assessment.status == "needs_clarification"
    assert assessment.error_code == "EMPTY_INPUT"
    assert llm.calls == []


def test_container_accepts_explicit_intent_dependencies() -> None:
    capability = _capability()
    catalog = FakeCatalog((capability,))
    retrieval = FakeCandidateRetrieval(_retrieval_result(capability.code))
    llm = FakeStructuredLlm(
        {
            "status": "matched",
            "capability_code": capability.code,
            "extracted_inputs": {"message": "hello"},
        }
    )
    container = ApplicationContainer(
        capability_catalog=catalog,
        capability_candidate_retrieval=retrieval,  # type: ignore[arg-type]
        intent_structured_llm=llm,
    )

    assessment = container.structured_intent_recognition().recognize(
        IntentRecognitionCommand("create a message")
    )
    confirmation = container.explicit_capability_confirmation().create_proposal(assessment)

    assert assessment.status == "matched"
    assert confirmation.status == "pending"
    assert confirmation.proposal is not None
    assert confirmation.proposal.capability_code == capability.code


def test_intent_recognition_does_not_import_execution_or_persistence_layers() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source_path = (
        project_root / "app" / "modules" / "interaction" / "application" / "intent_recognition.py"
    )
    imported_modules: set[str] = set()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden = (
        "app.modules.agent",
        "app.modules.online",
        "app.infrastructure.persistence",
    )
    assert not any(module.startswith(prefix) for module in imported_modules for prefix in forbidden)
