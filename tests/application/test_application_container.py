import asyncio
from unittest.mock import AsyncMock

from app.business.agents.tender.application.service import TenderApplication
from app.business.online.application.ask_knowledge import AskKnowledgeUseCase
from app.business.online.domain.checklist import COURT_EVALUATION_MATERIALS_SCENARIO
from app.composition import ApplicationContainer
from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.persistence.repositories.conversation_write_repository import (
    ConversationWriteRepository,
)
from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.shared.config import Settings


def test_application_container_registers_current_scenario_provider() -> None:
    container = ApplicationContainer(session=object())

    registry = container.checklist_data_provider_registry()

    assert registry.list_registered_scenarios() == (
        COURT_EVALUATION_MATERIALS_SCENARIO.scenario_code,
    )


def test_application_container_builds_online_services_with_shared_dependencies() -> None:
    container = ApplicationContainer(session=object())

    query_capability = container.knowledge_query_capability()
    decision_service = container.policy_decision_application_service()

    assert query_capability.read_port is container.knowledge_read_repository()
    assert decision_service.engine is container.checklist_decision_service()


def test_application_container_composes_use_cases_at_module_boundaries() -> None:
    container = ApplicationContainer(session=object())

    assert isinstance(container.ask_knowledge_use_case(), AskKnowledgeUseCase)
    assert container.ask_knowledge_use_case().facade is container.rag_application_facade()

    preview_use_case = container.ingestion_preview_use_case()
    ingest_use_case = container.ingestion_use_case()

    assert isinstance(preview_use_case, IngestionUseCase)
    assert isinstance(ingest_use_case, IngestionUseCase)
    assert isinstance(container.policy_candidate_scan_use_case(), PolicyCandidateScanUseCase)
    assert preview_use_case.pipeline.write_capability is None
    assert ingest_use_case.pipeline.write_capability is container.knowledge_write_capability()


def test_application_container_accepts_tender_llm_test_double() -> None:
    class FakeTenderLlm:
        def invoke(self, request: object, output_schema: object) -> object:
            return object()

    fake_llm = FakeTenderLlm()
    container = ApplicationContainer(session=object(), tender_structured_llm=fake_llm)

    assert container.tender_structured_llm() is fake_llm


def test_application_container_composes_tender_application_without_database() -> None:
    class FakeTenderLlm:
        def invoke(self, request: object, output_schema: object) -> object:
            return object()

    fake_llm = FakeTenderLlm()
    container = ApplicationContainer(tender_structured_llm=fake_llm)

    application = container.tender_application()

    assert isinstance(application, TenderApplication)
    assert application.llm is fake_llm


def test_application_container_shares_openai_client_factory_with_rag() -> None:
    factory = OpenAICompatibleClientFactory(
        configuration=Settings(
            zhipu_api_key="test-key",
            zhipu_base_url="https://example.com/v1",
            zhipu_chat_model="glm-test",
        )
    )
    container = ApplicationContainer(session=object(), openai_client_factory=factory)

    rag_service = container.rag_answer_service()

    assert rag_service.client is factory.create_client()


def test_application_container_shares_openai_client_factory_with_tender_agent() -> None:
    factory = OpenAICompatibleClientFactory(
        configuration=Settings(
            zhipu_api_key="test-key",
            zhipu_base_url="https://example.com/v1",
            zhipu_chat_model="glm-test",
        )
    )
    container = ApplicationContainer(session=object(), openai_client_factory=factory)

    tender_llm = container.tender_structured_llm()

    assert isinstance(tender_llm, LangChainGlmStructuredLlm)
    assert tender_llm._chat_model.root_client is factory.create_client()


def test_application_container_uses_conversation_port_for_dialogue_agent_invocation() -> None:
    container = ApplicationContainer(session=object())
    container.agent_call_dispatcher = lambda: object()  # type: ignore[method-assign]

    invocation = container.dialogue_agent_invocation()

    assert isinstance(invocation._conversation_write, ConversationWriteRepository)


def test_application_container_aclose_releases_openai_client_factory() -> None:
    factory = AsyncMock()
    container = ApplicationContainer(openai_client_factory=factory)

    asyncio.run(container.aclose())

    factory.aclose.assert_awaited_once_with()
