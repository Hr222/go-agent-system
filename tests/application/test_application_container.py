import asyncio
from unittest.mock import AsyncMock

import pytest

import app.composition.interaction as composition_interaction
import app.composition.root as composition_root
from app.business.agents.tender.application.service import TenderApplication
from app.business.online.application.ask_knowledge import AskKnowledgeUseCase
from app.business.online.domain.checklist import COURT_EVALUATION_MATERIALS_SCENARIO
from app.composition import ApplicationContainer
from app.composition.interaction import SessionScopedCapabilityCatalog
from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.persistence.repositories.conversation_write_repository import (
    ConversationWriteRepository,
)
from app.platform.conversation.application import ConversationContextBuilder
from app.platform.dialogue.application import (
    ConversationTurnCoordinator,
    StreamingConversationRuntime,
)
from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.platform.interaction.application.chat_stream import (
    InteractionStreamEvent,
    InteractionStreamPreparation,
)
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


def test_application_container_composes_streaming_runtime_with_history_context() -> None:
    class FakeStreamingChatLlm:
        def stream(self, request: object) -> object:
            del request
            raise AssertionError("测试不应启动模型流")

    coordinator = ConversationTurnCoordinator()
    container = ApplicationContainer(
        session=object(),
        streaming_chat_llm=FakeStreamingChatLlm(),  # type: ignore[arg-type]
        conversation_turn_coordinator=coordinator,
    )

    runtime = container.streaming_conversation_runtime()

    assert isinstance(runtime, StreamingConversationRuntime)
    assert runtime._conversation_persistence is container.streaming_conversation_persistence()
    assert isinstance(runtime._context_builder, ConversationContextBuilder)
    assert runtime._conversation_turn_coordinator is coordinator

    container.intent_interaction_gateway = lambda proposal_store: object()  # type: ignore[method-assign]
    container.dialogue_agent_invocation = lambda: object()  # type: ignore[method-assign]
    container.dialogue_agent_turn_executor = lambda: object()  # type: ignore[method-assign]
    interaction = container.interaction_chat_stream_application(
        proposal_store=object(),
        pending_agent_invocations=object(),
    )

    assert interaction._streaming_conversation is runtime
    assert interaction._dialogue_agent_turn_executor is not None


def test_streaming_runtime_accepts_async_persistence_without_request_session() -> None:
    class FakeStreamingChatLlm:
        def stream(self, request: object) -> object:
            del request
            raise AssertionError("测试不应启动模型流")

    persistence = object()
    container = ApplicationContainer(
        streaming_chat_llm=FakeStreamingChatLlm(),  # type: ignore[arg-type]
        streaming_conversation_persistence=persistence,  # type: ignore[arg-type]
    )

    runtime = container.streaming_conversation_runtime()

    assert container.session is None
    assert runtime._conversation_persistence is persistence


def test_stateless_application_container_uses_session_scoped_capability_catalog() -> None:
    container = ApplicationContainer()

    retrieval = container.capability_candidate_retrieval()

    assert isinstance(retrieval.capability_catalog, SessionScopedCapabilityCatalog)


def test_session_scoped_capability_catalog_closes_session_after_success(
    monkeypatch,
) -> None:  # noqa: ANN001
    class TrackingSession:
        def __init__(self) -> None:
            self.rollback_calls = 0
            self.close_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

        def close(self) -> None:
            self.close_calls += 1

    session = TrackingSession()
    class Catalog:
        def list_available(self, **kwargs):  # noqa: ANN003
            del kwargs
            return ("available",)

    catalog = Catalog()

    def repository_for(current_session):  # noqa: ANN001
        assert current_session is session
        return object()

    monkeypatch.setattr(
        composition_interaction,
        "build_capability_catalog_repository",
        repository_for,
    )
    monkeypatch.setattr(
        composition_interaction,
        "build_platform_capability_catalog",
        lambda _repository, _registry: catalog,
    )
    scoped_catalog = SessionScopedCapabilityCatalog(lambda: session)  # type: ignore[arg-type]

    assert scoped_catalog.list_available() == ("available",)
    assert session.rollback_calls == 0
    assert session.close_calls == 1


def test_session_scoped_capability_catalog_rolls_back_and_closes_on_failure(
    monkeypatch,
) -> None:  # noqa: ANN001
    class TrackingSession:
        def __init__(self) -> None:
            self.rollback_calls = 0
            self.close_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

        def close(self) -> None:
            self.close_calls += 1

    class FailingCatalog:
        def list_available(self, **kwargs):  # noqa: ANN003
            del kwargs
            raise RuntimeError("catalog unavailable")

    session = TrackingSession()

    def repository_for(current_session):  # noqa: ANN001
        assert current_session is session
        return object()

    monkeypatch.setattr(
        composition_interaction,
        "build_capability_catalog_repository",
        repository_for,
    )
    monkeypatch.setattr(
        composition_interaction,
        "build_platform_capability_catalog",
        lambda _repository, _registry: FailingCatalog(),
    )
    scoped_catalog = SessionScopedCapabilityCatalog(lambda: session)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="catalog unavailable"):
        scoped_catalog.list_available()

    assert session.rollback_calls == 1
    assert session.close_calls == 1


def test_interaction_preparation_worker_commits_before_closing_resources() -> None:
    events: list[str] = []

    class TrackingSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("session.close")

    class TrackingContainer:
        def close(self) -> None:
            events.append("container.close")

    class Application:
        def prepare(self, command):  # noqa: ANN001
            del command
            return InteractionStreamPreparation(
                kind="single_event",
                event=InteractionStreamEvent("result", {"status": "ready"}),
            )

    worker = composition_root._SessionScopedInteractionChatPreparationWorker(
        session=TrackingSession(),  # type: ignore[arg-type]
        container=TrackingContainer(),  # type: ignore[arg-type]
        application=Application(),  # type: ignore[arg-type]
    )

    worker.prepare(object())  # type: ignore[arg-type]
    worker.close()

    assert events == ["commit", "container.close", "session.close"]


def test_interaction_preparation_worker_rolls_back_controlled_failure() -> None:
    events: list[str] = []

    class TrackingSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("session.close")

    class TrackingContainer:
        def close(self) -> None:
            events.append("container.close")

    class Application:
        def prepare(self, command):  # noqa: ANN001
            del command
            return InteractionStreamPreparation(
                kind="single_event",
                event=InteractionStreamEvent("error", {"code": "FAILED"}),
            )

    worker = composition_root._SessionScopedInteractionChatPreparationWorker(
        session=TrackingSession(),  # type: ignore[arg-type]
        container=TrackingContainer(),  # type: ignore[arg-type]
        application=Application(),  # type: ignore[arg-type]
    )

    worker.prepare(object())  # type: ignore[arg-type]
    worker.close()

    assert events == ["rollback", "container.close", "session.close"]


def test_interaction_preparation_cancellation_commits_before_closing_resources() -> None:
    events: list[str] = []

    class TrackingSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("session.close")

    class TrackingContainer:
        def close(self) -> None:
            events.append("container.close")

    class Application:
        def prepare(self, command):  # noqa: ANN001
            del command
            return InteractionStreamPreparation(
                kind="single_event",
                event=InteractionStreamEvent(
                    "approval_required", {"proposal_id": "proposal-1"}
                ),
            )

        def cancel_preparation(self, command, preparation):  # noqa: ANN001
            del command, preparation
            events.append("cancel")

    worker = composition_root._SessionScopedInteractionChatPreparationWorker(
        session=TrackingSession(),  # type: ignore[arg-type]
        container=TrackingContainer(),  # type: ignore[arg-type]
        application=Application(),  # type: ignore[arg-type]
    )
    preparation = worker.prepare(object())  # type: ignore[arg-type]
    worker.cancel_preparation(object(), preparation)  # type: ignore[arg-type]
    worker.close()

    assert events == ["cancel", "commit", "container.close", "session.close"]


def test_interaction_preparation_cancellation_failure_rolls_back_before_closing() -> None:
    events: list[str] = []

    class TrackingSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("session.close")

    class TrackingContainer:
        def close(self) -> None:
            events.append("container.close")

    class Application:
        def cancel_preparation(self, command, preparation):  # noqa: ANN001
            del command, preparation
            raise RuntimeError("cancel persistence failed")

    worker = composition_root._SessionScopedInteractionChatPreparationWorker(
        session=TrackingSession(),  # type: ignore[arg-type]
        container=TrackingContainer(),  # type: ignore[arg-type]
        application=Application(),  # type: ignore[arg-type]
    )
    preparation = InteractionStreamPreparation(
        kind="single_event",
        event=InteractionStreamEvent("approval_required", {"proposal_id": "proposal-1"}),
    )

    with pytest.raises(RuntimeError, match="cancel persistence failed"):
        worker.cancel_preparation(object(), preparation)  # type: ignore[arg-type]
    worker.close()

    assert events == ["rollback", "container.close", "session.close"]


def test_application_container_aclose_releases_openai_client_factory() -> None:
    factory = AsyncMock()
    container = ApplicationContainer(openai_client_factory=factory)

    asyncio.run(container.aclose())

    factory.aclose.assert_awaited_once_with()


def test_private_agent_turn_worker_closes_its_container_and_session(monkeypatch) -> None:  # noqa: ANN001
    class TrackingSession:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    class TrackingWorker:
        def __init__(self) -> None:
            self.closed = 0

        def execute(self, command):  # noqa: ANN001
            return command

        def close(self) -> None:
            self.closed += 1

    class TrackingContainer:
        instances: list["TrackingContainer"] = []

        def __init__(self, session) -> None:  # noqa: ANN001
            self.session = session
            self.worker = TrackingWorker()
            self.aclose_calls = 0
            self.instances.append(self)

        def dialogue_agent_turn_worker(self) -> TrackingWorker:
            return self.worker

        async def aclose(self) -> None:
            self.aclose_calls += 1

    session = TrackingSession()
    monkeypatch.setattr(composition_root, "SessionLocal", lambda: session)
    monkeypatch.setattr(composition_root, "ApplicationContainer", TrackingContainer)

    worker = composition_root._SessionScopedDialogueAgentTurnWorkerFactory().create()

    assert worker.execute("agent-command") == "agent-command"
    worker.close()
    worker.close()

    container = TrackingContainer.instances[0]
    assert container.worker.closed == 1
    assert container.aclose_calls == 1
    assert session.closed == 1


def test_private_agent_turn_worker_factory_closes_async_resources_on_setup_failure(
    monkeypatch,
) -> None:  # noqa: ANN001
    class TrackingSession:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    class FailingContainer:
        instances: list["FailingContainer"] = []

        def __init__(self, session) -> None:  # noqa: ANN001
            self.session = session
            self.aclose_calls = 0
            self.instances.append(self)

        def dialogue_agent_turn_worker(self) -> object:
            raise RuntimeError("worker setup failed")

        async def aclose(self) -> None:
            self.aclose_calls += 1

    session = TrackingSession()
    monkeypatch.setattr(composition_root, "SessionLocal", lambda: session)
    monkeypatch.setattr(composition_root, "ApplicationContainer", FailingContainer)

    with pytest.raises(RuntimeError, match="worker setup failed"):
        composition_root._SessionScopedDialogueAgentTurnWorkerFactory().create()

    assert FailingContainer.instances[0].aclose_calls == 1
    assert session.closed == 1
