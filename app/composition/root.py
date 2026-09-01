from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path

from sqlalchemy.orm import Session

from app.business.agents.tender.application.service import TenderApplication
from app.business.online.application.ask_knowledge import AskKnowledgeUseCase
from app.business.online.application.data_acquisition import (
    ChecklistDataProviderRegistry,
    InlineChecklistDataProvider,
    PolicyDataAcquisitionService,
)
from app.business.online.application.decision import (
    RuleDrivenChecklistDecisionService,
)
from app.business.online.application.policy_decision import PolicyDecisionApplicationService
from app.business.online.application.rag_facade import RagApplicationFacade
from app.business.online.application.rule_retrieval import PolicyRuleRetrievalService
from app.business.online.domain.checklist import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
    ChecklistScenarioRegistry,
    RuleDrivenChecklistPolicy,
)
from app.composition.agent import build_tender_application, build_tender_structured_llm
from app.composition.attachment import build_attachment_storage
from app.composition.conversation import (
    build_conversation_access_service,
    build_conversation_context_builder,
    build_conversation_event_repository,
    build_conversation_history_read_service,
    build_conversation_list_read_service,
    build_conversation_management_service,
    build_conversation_recent_message_read_service,
    build_conversation_topic_summary_update_service,
    build_conversation_write_repository,
    build_conversation_write_service,
)
from app.composition.dialogue import build_streaming_conversation_runtime
from app.composition.ingestion import (
    build_ingestion_service,
    build_ingestion_use_case,
    build_pipeline,
    build_policy_candidate_scan_use_case,
    build_retry_ingestion_use_case,
    build_upload_service,
)
from app.composition.intent import (
    build_explicit_capability_confirmation,
    build_intent_interaction_gateway,
    build_structured_intent_recognition,
)
from app.composition.interaction import (
    SessionScopedCapabilityCatalog,
    build_agent_call_dispatcher,
    build_agent_runtime,
    build_capability_candidate_retrieval,
    build_capability_catalog_repository,
    build_capability_dispatch_registry,
    build_controlled_dispatcher,
    build_platform_capability_catalog,
)
from app.composition.knowledge import (
    build_knowledge_base_service,
    build_knowledge_management_service,
    build_persistence_gateway,
    build_publication_service,
    build_query_capability,
    build_read_repository,
    build_write_capability,
    build_write_repository,
)
from app.composition.llm import build_chat_llm, build_streaming_chat_llm, build_structured_llm
from app.composition.online import (
    build_decision_service,
    build_policy_decision_application_service,
    build_rag_facade,
    build_rule_retrieval_service,
)
from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.infrastructure.filesystem.policy_file_service import PolicyFileService
from app.infrastructure.filesystem.upload_service import PolicyUploadService
from app.infrastructure.llm.embedding_client import GiteeEmbeddingClient
from app.infrastructure.llm.llm_client import LazyRagAnswerGenerator, RagAnswerGenerator
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.ocr.tencent_ocr import PolicyOcrService
from app.infrastructure.persistence.repositories.knowledge_read_repository import (
    KnowledgeReadRepository,
)
from app.infrastructure.persistence.repositories.knowledge_write_repository import (
    KnowledgeWriteRepository,
)
from app.infrastructure.persistence.repositories.policy_persistence_gateway import (
    PolicyPersistenceGateway,
)
from app.infrastructure.persistence.session import SessionLocal
from app.interfaces.agent import FunctionCallingAdapter
from app.platform.agent.runtime import AgentRuntime
from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationHistoryReadService,
    ConversationListReadService,
    ConversationManagementService,
    ConversationResolveQuery,
    ConversationTopicSummaryUpdateService,
)
from app.platform.conversation.domain import Message, MessageRole
from app.platform.conversation.ports import ConversationRecentMessageWindow
from app.platform.dialogue.application import (
    AgentResultProjector,
    ConversationTurnCoordinator,
    DialogueAgentContinuationService,
    DialogueAgentInvocationService,
    DialogueAgentTurnExecutor,
    DialogueAgentTurnWorker,
    DialogueAgentTurnWorkerFactoryPort,
    DialogueAgentTurnWorkerPort,
    StreamingConversationRuntime,
    ThreadedStreamingConversationPersistence,
)
from app.platform.dialogue.ports import (
    StreamingConversationPersistencePort,
    StreamingConversationPersistenceWorkerFactoryPort,
    StreamingConversationPersistenceWorkerPort,
)
from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.platform.ingestion.pipeline import PolicyIngestionService
from app.platform.interaction.application.agent_dispatch import AgentCallDispatcher
from app.platform.interaction.application.candidate_retrieval import CapabilityCandidateRetrieval
from app.platform.interaction.application.catalog import PlatformCapabilityCatalog
from app.platform.interaction.application.chat_preparation import ThreadedInteractionChatPreparation
from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
    InteractionStreamPreparation,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.gateway import IntentInteractionGateway
from app.platform.interaction.application.intent_recognition import StructuredIntentRecognition
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.interaction.ports.proposal_store import PendingProposalStorePort
from app.platform.knowledge import KnowledgeBaseQueryCapability, KnowledgePublicationService
from app.platform.knowledge.application.knowledge_base import KnowledgeBaseService
from app.platform.knowledge.application.management_service import KnowledgeManagementService
from app.platform.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.platform.llm.application.chat import ChatApplication
from app.platform.llm.application.streaming_chat import StreamingChatApplication
from app.platform.llm.contracts import ChatLlmPort, StreamingChatLlmPort, StructuredLlmPort
from app.shared.config import settings


def get_db_session() -> Generator[Session, None, None]:
    """为 HTTP 依赖提供器提供数据库会话生命周期。"""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class ApplicationContainer:
    """Composition Root，只负责装配端口、适配器与应用用例。

    所有具体基础设施实现都在这里实例化，业务模块只接收能力端口，
    这样 HTTP、Agent 和测试替身可以共享同一套应用层装配规则。
    """

    def __init__(
        self,
        session: Session | None = None,
        *,
        attachment_storage: FilesystemAttachmentStorage | None = None,
        scenario_registry: ChecklistScenarioRegistry | None = None,
        checklist_policy: RuleDrivenChecklistPolicy | None = None,
        data_provider_registry: ChecklistDataProviderRegistry | None = None,
        answer_service: RagAnswerGenerator | None = None,
        tender_structured_llm: StructuredLlmPort | None = None,
        intent_structured_llm: StructuredLlmPort | None = None,
        chat_llm: ChatLlmPort | None = None,
        streaming_chat_llm: StreamingChatLlmPort | None = None,
        conversation_turn_coordinator: ConversationTurnCoordinator | None = None,
        streaming_conversation_persistence: StreamingConversationPersistencePort | None = None,
        openai_client_factory: OpenAICompatibleClientFactory | None = None,
        capability_catalog: CapabilityCatalogPort | None = None,
        capability_candidate_retrieval: CapabilityCandidateRetrieval | None = None,
    ) -> None:
        self.session = session
        self.scenario_registry = scenario_registry or ChecklistScenarioRegistry(
            definitions=(COURT_EVALUATION_MATERIALS_SCENARIO,),
            default_scenario_code=COURT_EVALUATION_MATERIALS_SCENARIO.scenario_code,
        )
        self.checklist_policy = checklist_policy or RuleDrivenChecklistPolicy()
        self._data_provider_registry = data_provider_registry
        self._answer_service = answer_service
        self._tender_structured_llm = tender_structured_llm
        self._intent_structured_llm = intent_structured_llm
        self._tender_application: TenderApplication | None = None
        self._chat_llm = chat_llm
        self._chat_application: ChatApplication | None = None
        self._streaming_chat_llm = streaming_chat_llm
        self._streaming_conversation_persistence = streaming_conversation_persistence
        self._conversation_turn_coordinator = (
            conversation_turn_coordinator
            if conversation_turn_coordinator is not None
            else ConversationTurnCoordinator()
        )
        self._streaming_chat_application: StreamingChatApplication | None = None
        self._streaming_conversation_runtime: StreamingConversationRuntime | None = None
        self._streaming_interaction_chat_stream_application: (
            InteractionChatStreamApplication | None
        ) = None
        self._openai_client_factory = openai_client_factory
        self._persistence_gateway: PolicyPersistenceGateway | None = None
        self._write_repository: KnowledgeWriteRepository | None = None
        self._write_capability: KnowledgeBaseWriteCapability | None = None
        self._read_repository: KnowledgeReadRepository | None = None
        self._rule_retrieval_service: PolicyRuleRetrievalService | None = None
        self._data_acquisition_service: PolicyDataAcquisitionService | None = None
        self._decision_service: RuleDrivenChecklistDecisionService | None = None
        self._decision_application_service: PolicyDecisionApplicationService | None = None
        self._knowledge_query: KnowledgeBaseQueryCapability | None = None
        self._rag_facade: RagApplicationFacade | None = None
        self._publication_service: KnowledgePublicationService | None = None
        self._ingestion_preview_use_case: IngestionUseCase | None = None
        self._ingestion_use_case: IngestionUseCase | None = None
        self._retry_ingestion_use_case: RetryIngestionUseCase | None = None
        self._ask_knowledge_use_case: AskKnowledgeUseCase | None = None
        self._policy_upload_service: PolicyUploadService | None = None
        self._attachment_storage = attachment_storage
        self._policy_ingestion_service: PolicyIngestionService | None = None
        self._policy_candidate_scan_use_case: PolicyCandidateScanUseCase | None = None
        self._knowledge_base_service: KnowledgeBaseService | None = None
        self._knowledge_management_service: KnowledgeManagementService | None = None
        self._embedding_service: GiteeEmbeddingClient | None = None
        self._file_service: PolicyFileService | None = None
        self._ocr_service: PolicyOcrService | None = None
        self._capability_catalog = capability_catalog
        self._capability_catalog_repository = None
        self._capability_dispatch_registry = None
        self._agent_runtime: AgentRuntime | None = None
        self._agent_call_dispatcher: AgentCallDispatcher | None = None
        self._dialogue_agent_invocation: DialogueAgentInvocationService | None = None
        self._dialogue_agent_continuation: DialogueAgentContinuationService | None = None
        self._dialogue_agent_turn_worker: DialogueAgentTurnWorker | None = None
        self._dialogue_agent_turn_executor: DialogueAgentTurnExecutor | None = None
        self._conversation_access: ConversationAccessService | None = None
        self._conversation_history_read: ConversationHistoryReadService | None = None
        self._conversation_list_read: ConversationListReadService | None = None
        self._conversation_management: ConversationManagementService | None = None
        self._capability_candidate_retrieval: CapabilityCandidateRetrieval | None = None
        self._structured_intent_recognition: StructuredIntentRecognition | None = None
        self._explicit_capability_confirmation: ExplicitCapabilityConfirmation | None = None
        if capability_candidate_retrieval is not None:
            self._capability_candidate_retrieval = capability_candidate_retrieval

    def tender_structured_llm(self) -> StructuredLlmPort:
        """延迟组装招标书 Agent 使用的结构化 LLM 能力。"""

        if self._tender_structured_llm is None:
            self._tender_structured_llm = build_tender_structured_llm(
                self.openai_client_factory()
            )
        return self._tender_structured_llm

    def tender_application(self) -> TenderApplication:
        """提供不依赖数据库会话的同步 Tender Agent 用例。"""

        if self._tender_application is None:
            self._tender_application = build_tender_application(self.tender_structured_llm())
        return self._tender_application

    def platform_capability_catalog(self) -> PlatformCapabilityCatalog | CapabilityCatalogPort:
        if self._capability_catalog is None:
            if self.session is None:
                raise RuntimeError("平台能力目录需要数据库 session，但容器未提供 session。")
            if self._capability_catalog_repository is None:
                self._capability_catalog_repository = build_capability_catalog_repository(
                    self.session
                )
            if self._capability_dispatch_registry is None:
                self._capability_dispatch_registry = build_capability_dispatch_registry()
            self._capability_catalog = build_platform_capability_catalog(
                self._capability_catalog_repository,
                self._capability_dispatch_registry,
            )
        return self._capability_catalog

    def agent_runtime(self) -> AgentRuntime:
        if self._agent_runtime is None:
            self._agent_runtime = build_agent_runtime(
                self.platform_capability_catalog(),
                tender_application=self.tender_application,
            )
        return self._agent_runtime

    def agent_call_dispatcher(self) -> AgentCallDispatcher:
        """提供后续 Dialogue Runtime 使用的 V2 受控 Agent 分发服务。"""

        if self._agent_call_dispatcher is None:
            self._agent_call_dispatcher = build_agent_call_dispatcher(
                self.platform_capability_catalog(),
                agent_runtime=self.agent_runtime,
                artifact_storage=self.attachment_storage(),
            )
        return self._agent_call_dispatcher

    def dialogue_agent_invocation(self) -> DialogueAgentInvocationService:
        """组装 V2 对话到 Agent 的一次调用服务。"""

        if self.session is None:
            raise RuntimeError("对话 Agent 调用需要数据库 session，但容器未提供 session。")
        if self._dialogue_agent_invocation is None:
            self._dialogue_agent_invocation = DialogueAgentInvocationService(
                conversation_access=self.conversation_access(),
                conversation_write=build_conversation_write_repository(self.session),
                topic_summary_writer=build_conversation_write_service(self.session),
                event_write=build_conversation_event_repository(self.session),
                dispatcher=self.agent_call_dispatcher(),
                projector=AgentResultProjector(),
            )
        return self._dialogue_agent_invocation

    def dialogue_agent_continuation(self) -> DialogueAgentContinuationService:
        if self.session is None:
            raise RuntimeError("对话 Agent 续写需要数据库 session，但容器未提供。")
        if self._dialogue_agent_continuation is None:
            self._dialogue_agent_continuation = DialogueAgentContinuationService(
                conversation_access=self.conversation_access(),
                conversation_read=build_conversation_history_read_service(self.session),
                event_read=build_conversation_event_repository(self.session),
                conversation_write=build_conversation_write_service(self.session),
                context_builder=build_conversation_context_builder(),
                llm=self.chat_application().llm,
            )
        return self._dialogue_agent_continuation

    def dialogue_agent_turn_worker(self) -> DialogueAgentTurnWorker:
        """组装只在私有同步 worker 内使用的 Agent 事实链执行器。"""

        if self.session is None:
            raise RuntimeError("对话 Agent 轮次需要数据库 session，但容器未提供。")
        if self._dialogue_agent_turn_worker is None:
            self._dialogue_agent_turn_worker = DialogueAgentTurnWorker(
                invocation=self.dialogue_agent_invocation(),
                continuation=self.dialogue_agent_continuation(),
            )
        return self._dialogue_agent_turn_worker

    def dialogue_agent_turn_executor(self) -> DialogueAgentTurnExecutor:
        """提供持有会话租约并异步监督私有 Agent worker 的 Dialogue 用例。"""

        if self._dialogue_agent_turn_executor is None:
            self._dialogue_agent_turn_executor = DialogueAgentTurnExecutor(
                coordinator=self._conversation_turn_coordinator,
                worker_factory=_SessionScopedDialogueAgentTurnWorkerFactory(),
            )
        return self._dialogue_agent_turn_executor

    def conversation_access(self) -> ConversationAccessService:
        if self.session is None:
            raise RuntimeError("会话访问需要数据库 session，但容器未提供。")
        if self._conversation_access is None:
            self._conversation_access = build_conversation_access_service(self.session)
        return self._conversation_access

    def conversation_topic_summary_update(self) -> ConversationTopicSummaryUpdateService:
        if self.session is None:
            raise RuntimeError("会话话题概括修改需要数据库 session，但容器未提供。")
        return build_conversation_topic_summary_update_service(self.session)

    def conversation_history_read(self) -> ConversationHistoryReadService:
        if self.session is None:
            raise RuntimeError("会话历史读取需要数据库 session，但容器未提供。")
        if self._conversation_history_read is None:
            self._conversation_history_read = build_conversation_history_read_service(
                self.session
            )
        return self._conversation_history_read

    def conversation_list_read(self) -> ConversationListReadService:
        if self.session is None:
            raise RuntimeError("会话列表读取需要数据库 session，但容器未提供。")
        if self._conversation_list_read is None:
            self._conversation_list_read = build_conversation_list_read_service(self.session)
        return self._conversation_list_read

    def conversation_management(self) -> ConversationManagementService:
        if self.session is None:
            raise RuntimeError("会话管理需要数据库 session，但容器未提供。")
        if self._conversation_management is None:
            self._conversation_management = build_conversation_management_service(self.session)
        return self._conversation_management

    def capability_candidate_retrieval(self) -> CapabilityCandidateRetrieval:
        if self._capability_candidate_retrieval is None:
            capability_catalog = (
                self.platform_capability_catalog()
                if self.session is not None
                else SessionScopedCapabilityCatalog(SessionLocal)
            )
            self._capability_candidate_retrieval = build_capability_candidate_retrieval(
                capability_catalog,
                self.embedding_service(),
            )
        return self._capability_candidate_retrieval

    def intent_structured_llm(self) -> StructuredLlmPort:
        if self._intent_structured_llm is None:
            self._intent_structured_llm = build_structured_llm(self.openai_client_factory())
        return self._intent_structured_llm

    def structured_intent_recognition(
        self,
        *,
        capability_candidate_retrieval: CapabilityCandidateRetrieval | None = None,
    ) -> StructuredIntentRecognition:
        if self._structured_intent_recognition is None:
            self._structured_intent_recognition = build_structured_intent_recognition(
                capability_candidate_retrieval or self.capability_candidate_retrieval(),
                self.platform_capability_catalog(),
                self.intent_structured_llm(),
            )
        return self._structured_intent_recognition

    def explicit_capability_confirmation(self) -> ExplicitCapabilityConfirmation:
        if self._explicit_capability_confirmation is None:
            self._explicit_capability_confirmation = build_explicit_capability_confirmation(
                self.platform_capability_catalog()
            )
        return self._explicit_capability_confirmation

    def intent_interaction_gateway(
        self,
        proposal_store: PendingProposalStorePort,
        *,
        capability_candidate_retrieval: CapabilityCandidateRetrieval | None = None,
    ) -> IntentInteractionGateway:
        candidate_retrieval = (
            capability_candidate_retrieval or self.capability_candidate_retrieval()
        )
        dispatcher = build_controlled_dispatcher(
            self.platform_capability_catalog(),
            agent_runtime=self.agent_runtime,
            chat_application=self.chat_application,
            ask_knowledge_use_case=self.ask_knowledge_use_case,
            policy_decision_application_service=self.policy_decision_application_service,
        )
        return build_intent_interaction_gateway(
            candidate_retrieval=candidate_retrieval,
            intent_recognition=self.structured_intent_recognition(
                capability_candidate_retrieval=candidate_retrieval,
            ),
            confirmation=self.explicit_capability_confirmation(),
            proposal_store=proposal_store,
            dispatcher=dispatcher,
            attachment_reader=self.attachment_storage(),
        )

    def interaction_chat_stream_application(
        self,
        proposal_store: PendingProposalStorePort,
        pending_agent_invocations=None,  # noqa: ANN001
    ) -> InteractionChatStreamApplication:
        return InteractionChatStreamApplication(
            self.intent_interaction_gateway(proposal_store),
            self.streaming_conversation_runtime(),
            dialogue_agent_invocation=self.dialogue_agent_invocation(),
            pending_agent_invocations=pending_agent_invocations,
            dialogue_agent_turn_executor=self.dialogue_agent_turn_executor(),
        )

    def streaming_interaction_chat_stream_application(
        self,
        proposal_store: PendingProposalStorePort,
        pending_agent_invocations=None,  # noqa: ANN001
    ) -> InteractionChatStreamApplication:
        """提供不携带请求级数据库资源的进程级普通流式 Chat 应用。"""

        if self._streaming_interaction_chat_stream_application is None:
            streaming_conversation = self.streaming_conversation_runtime()
            self._streaming_interaction_chat_stream_application = InteractionChatStreamApplication(
                gateway=None,
                streaming_conversation=streaming_conversation,
                preparation=ThreadedInteractionChatPreparation(
                    _SessionScopedInteractionChatPreparationWorkerFactory(
                        capability_candidate_retrieval=self.capability_candidate_retrieval(),
                        intent_structured_llm=self.intent_structured_llm(),
                        attachment_storage=self.attachment_storage(),
                        proposal_store=proposal_store,
                        pending_agent_invocations=pending_agent_invocations,
                        streaming_conversation=streaming_conversation,
                    )
                ),
            )
        return self._streaming_interaction_chat_stream_application

    def chat_application(self) -> ChatApplication:
        """提供无数据库依赖的独立单轮 LLM Chat 用例。"""

        if self._chat_application is None:
            if self._chat_llm is None:
                self._chat_llm = build_chat_llm(self.openai_client_factory())
            self._chat_application = ChatApplication(self._chat_llm)
        return self._chat_application

    def streaming_chat_application(self) -> StreamingChatApplication:
        """提供无数据库依赖的独立单轮 LLM 流式用例。"""

        if self._streaming_chat_application is None:
            if self._streaming_chat_llm is None:
                self._streaming_chat_llm = build_streaming_chat_llm(
                    self.openai_client_factory()
                )
            self._streaming_chat_application = StreamingChatApplication(
                self._streaming_chat_llm
            )
        return self._streaming_chat_application

    def streaming_conversation_runtime(self) -> StreamingConversationRuntime:
        """提供依赖 Conversation 事实写入的流式 Dialogue 用例。"""

        if self._streaming_conversation_runtime is None:
            if self._streaming_chat_llm is None:
                self._streaming_chat_llm = build_streaming_chat_llm(
                    self.openai_client_factory()
                )
            self._streaming_conversation_runtime = build_streaming_conversation_runtime(
                self._streaming_chat_llm,
                conversation_turn_coordinator=self._conversation_turn_coordinator,
                conversation_persistence=self.streaming_conversation_persistence(),
                context_builder=build_conversation_context_builder(),
            )
        return self._streaming_conversation_runtime

    def streaming_conversation_persistence(self) -> StreamingConversationPersistencePort:
        """为普通流式 Chat 提供不复用 HTTP Session 的异步持久化边界。"""

        if self._streaming_conversation_persistence is None:
            self._streaming_conversation_persistence = ThreadedStreamingConversationPersistence(
                _SessionScopedStreamingConversationPersistenceWorkerFactory()
            )
        return self._streaming_conversation_persistence

    def openai_client_factory(self) -> OpenAICompatibleClientFactory:
        """返回供 RAG 和 Agent 共享的 OpenAI-compatible Client Factory。"""

        if self._openai_client_factory is None:
            self._openai_client_factory = OpenAICompatibleClientFactory(
                provider=settings.llm_provider
            )
        return self._openai_client_factory

    def close(self) -> None:
        try:
            if self._openai_client_factory is not None:
                self._openai_client_factory.close()
        finally:
            if self._embedding_service is not None:
                self._embedding_service.close()

    async def aclose(self) -> None:
        """关闭 Container 创建的异步基础设施资源。"""

        try:
            if self._openai_client_factory is not None:
                await self._openai_client_factory.aclose()
        finally:
            if self._embedding_service is not None:
                self._embedding_service.close()

    def embedding_service(self) -> GiteeEmbeddingClient:
        if self._embedding_service is None:
            self._embedding_service = GiteeEmbeddingClient()
        return self._embedding_service

    def file_service(self) -> PolicyFileService:
        if self._file_service is None:
            self._file_service = PolicyFileService()
        return self._file_service

    def ocr_service(self) -> PolicyOcrService:
        if self._ocr_service is None:
            self._ocr_service = PolicyOcrService()
        return self._ocr_service

    def persistence_gateway(self) -> PolicyPersistenceGateway:
        if self.session is None:
            raise RuntimeError("当前能力需要数据库会话，但容器未提供 session。")
        if self._persistence_gateway is None:
            self._persistence_gateway = build_persistence_gateway(self.session)
        return self._persistence_gateway

    def knowledge_write_repository(self) -> KnowledgeWriteRepository:
        if self._write_repository is None:
            self._write_repository = build_write_repository(self.persistence_gateway())
        return self._write_repository

    def knowledge_write_capability(self) -> KnowledgeBaseWriteCapability:
        if self._write_capability is None:
            self._write_capability = build_write_capability(self.knowledge_write_repository())
        return self._write_capability

    def knowledge_read_repository(self) -> KnowledgeReadRepository:
        if self._read_repository is None:
            self._read_repository = build_read_repository(
                self.persistence_gateway(),
                embedding_service=self.embedding_service(),
            )
        return self._read_repository

    def knowledge_query_capability(self) -> KnowledgeBaseQueryCapability:
        if self._knowledge_query is None:
            self._knowledge_query = build_query_capability(self.knowledge_read_repository())
        return self._knowledge_query

    def rag_answer_service(self) -> RagAnswerGenerator:
        if self._answer_service is None:
            self._answer_service = RagAnswerGenerator(
                client_factory=self.openai_client_factory()
            )
        return self._answer_service

    def rag_application_facade(self) -> RagApplicationFacade:
        if self._rag_facade is None:
            # 未注入测试替身时延迟创建 LLM 客户端，保证只使用检索能力的接口不被配置阻塞。
            if self._answer_service is not None:
                answer_generator = self._answer_service
            else:
                answer_generator = LazyRagAnswerGenerator(self.rag_answer_service)
            self._rag_facade = build_rag_facade(self.knowledge_query_capability(), answer_generator)
        return self._rag_facade

    def ask_knowledge_use_case(self) -> AskKnowledgeUseCase:
        if self._ask_knowledge_use_case is None:
            self._ask_knowledge_use_case = AskKnowledgeUseCase(self.rag_application_facade())
        return self._ask_knowledge_use_case

    def function_calling_adapter(self) -> FunctionCallingAdapter:
        return FunctionCallingAdapter(self.ask_knowledge_use_case())

    def checklist_data_provider_registry(self) -> ChecklistDataProviderRegistry:
        if self._data_provider_registry is None:
            provider = InlineChecklistDataProvider()
            registry = ChecklistDataProviderRegistry(default_provider=provider)
            for scenario in self.scenario_registry.list_all():
                registry.register(scenario.scenario_code, provider)
            self._data_provider_registry = registry
        return self._data_provider_registry

    def policy_rule_retrieval_service(self) -> PolicyRuleRetrievalService:
        if self._rule_retrieval_service is None:
            self._rule_retrieval_service = build_rule_retrieval_service(
                self.knowledge_query_capability(),
                scenario_registry=self.scenario_registry,
                checklist_policy=self.checklist_policy,
            )
        return self._rule_retrieval_service

    def policy_data_acquisition_service(self) -> PolicyDataAcquisitionService:
        if self._data_acquisition_service is None:
            self._data_acquisition_service = PolicyDataAcquisitionService(
                self.checklist_data_provider_registry(),
                scenario_registry=self.scenario_registry,
            )
        return self._data_acquisition_service

    def checklist_decision_service(self) -> RuleDrivenChecklistDecisionService:
        if self._decision_service is None:
            self._decision_service = build_decision_service(
                self.knowledge_query_capability(),
                checklist_policy=self.checklist_policy,
                scenario_registry=self.scenario_registry,
                rule_retrieval_service=self.policy_rule_retrieval_service(),
                data_acquisition_service=self.policy_data_acquisition_service(),
            )
        return self._decision_service

    def policy_decision_application_service(self) -> PolicyDecisionApplicationService:
        if self._decision_application_service is None:
            self._decision_application_service = build_policy_decision_application_service(
                self.checklist_decision_service()
            )
        return self._decision_application_service

    def knowledge_publication_service(self) -> KnowledgePublicationService:
        if self._publication_service is None:
            self._publication_service = build_publication_service(
                self.persistence_gateway().session
            )
        return self._publication_service

    def ingestion_preview_use_case(self) -> IngestionUseCase:
        if self._ingestion_preview_use_case is None:
            self._ingestion_preview_use_case = build_ingestion_use_case(
                build_pipeline(
                    file_service=self.file_service(),
                    ocr_service=self.ocr_service(),
                )
            )
        return self._ingestion_preview_use_case

    def ingestion_use_case(self) -> IngestionUseCase:
        if self._ingestion_use_case is None:
            self._ingestion_use_case = build_ingestion_use_case(
                build_pipeline(
                    write_capability=self.knowledge_write_capability(),
                    embedding_service=self.embedding_service(),
                    file_service=self.file_service(),
                    ocr_service=self.ocr_service(),
                )
            )
        return self._ingestion_use_case

    def retry_ingestion_use_case(self) -> RetryIngestionUseCase:
        if self._retry_ingestion_use_case is None:
            self._retry_ingestion_use_case = build_retry_ingestion_use_case(
                self.ingestion_use_case(),
                self.persistence_gateway(),
            )
        return self._retry_ingestion_use_case

    def policy_upload_service(self) -> PolicyUploadService:
        if self._policy_upload_service is None:
            self._policy_upload_service = build_upload_service(
                Path(settings.policy_pipeline_workspace)
            )
        return self._policy_upload_service

    def attachment_storage(self) -> FilesystemAttachmentStorage:
        if self._attachment_storage is None:
            self._attachment_storage = build_attachment_storage(
                Path(settings.attachment_storage_workspace)
            )
        return self._attachment_storage

    def policy_ingestion_service(self) -> PolicyIngestionService:
        if self._policy_ingestion_service is None:
            self._policy_ingestion_service = build_ingestion_service()
        return self._policy_ingestion_service

    def policy_candidate_scan_use_case(self) -> PolicyCandidateScanUseCase:
        if self._policy_candidate_scan_use_case is None:
            self._policy_candidate_scan_use_case = (
                build_policy_candidate_scan_use_case(self.policy_ingestion_service())
            )
        return self._policy_candidate_scan_use_case

    def knowledge_base_service(self) -> KnowledgeBaseService:
        if self._knowledge_base_service is None:
            self._knowledge_base_service = build_knowledge_base_service(
                self.knowledge_read_repository()
            )
        return self._knowledge_base_service

    def knowledge_management_service(self) -> KnowledgeManagementService:
        if self._knowledge_management_service is None:
            self._knowledge_management_service = build_knowledge_management_service(
                self.knowledge_read_repository()
            )
        return self._knowledge_management_service


class _SessionScopedDialogueAgentTurnWorkerFactory(DialogueAgentTurnWorkerFactoryPort):
    """在 worker 线程中创建独立容器，避免复用 HTTP 请求的 Session。"""

    def create(self) -> DialogueAgentTurnWorkerPort:
        session = SessionLocal()
        container = ApplicationContainer(session)
        try:
            worker = container.dialogue_agent_turn_worker()
        except BaseException:
            try:
                asyncio.run(container.aclose())
            finally:
                session.close()
            raise
        return _SessionScopedDialogueAgentTurnWorker(
            worker=worker,
            container=container,
            session=session,
        )


class _SessionScopedDialogueAgentTurnWorker(DialogueAgentTurnWorkerPort):
    """将私有 Container 与 Session 的关闭收口到一次 Agent worker 执行。"""

    def __init__(
        self,
        *,
        worker: DialogueAgentTurnWorkerPort,
        container: ApplicationContainer,
        session: Session,
    ) -> None:
        self._worker = worker
        self._container = container
        self._session = session
        self._closed = False

    def execute(self, command):  # noqa: ANN001
        return self._worker.execute(command)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._worker.close()
        finally:
            try:
                asyncio.run(self._container.aclose())
            finally:
                self._session.close()


class _SessionScopedStreamingConversationPersistenceWorkerFactory(
    StreamingConversationPersistenceWorkerFactoryPort
):
    """为每次短操作创建独立 Session，避免数据库连接跨模型流占用。"""

    def create(self) -> StreamingConversationPersistenceWorkerPort:
        session = SessionLocal()
        try:
            return _SessionScopedStreamingConversationPersistenceWorker(session)
        except BaseException:
            try:
                session.rollback()
            finally:
                session.close()
            raise


class _SessionScopedInteractionChatPreparationWorkerFactory:
    """在准备 Worker 内创建 Gateway，避免把请求 Session 带入进程级应用。"""

    def __init__(
        self,
        *,
        capability_candidate_retrieval: CapabilityCandidateRetrieval,
        intent_structured_llm: StructuredLlmPort,
        attachment_storage: FilesystemAttachmentStorage,
        proposal_store: PendingProposalStorePort,
        pending_agent_invocations: object | None,
        streaming_conversation: StreamingConversationRuntime,
    ) -> None:
        self._capability_candidate_retrieval = capability_candidate_retrieval
        self._intent_structured_llm = intent_structured_llm
        self._attachment_storage = attachment_storage
        self._proposal_store = proposal_store
        self._pending_agent_invocations = pending_agent_invocations
        self._streaming_conversation = streaming_conversation

    def create(self) -> "_SessionScopedInteractionChatPreparationWorker":
        session = SessionLocal()
        try:
            container = ApplicationContainer(
                session,
                attachment_storage=self._attachment_storage,
                intent_structured_llm=self._intent_structured_llm,
                capability_candidate_retrieval=self._capability_candidate_retrieval,
            )
            gateway = container.intent_interaction_gateway(self._proposal_store)
            dialogue_agent_invocation = (
                container.dialogue_agent_invocation()
                if self._pending_agent_invocations is not None
                else None
            )
            application = InteractionChatStreamApplication(
                gateway,
                self._streaming_conversation,
                dialogue_agent_invocation=dialogue_agent_invocation,
                pending_agent_invocations=self._pending_agent_invocations,
            )
            return _SessionScopedInteractionChatPreparationWorker(
                session=session,
                container=container,
                application=application,
            )
        except BaseException:
            session.rollback()
            session.close()
            raise


class _SessionScopedInteractionChatPreparationWorker:
    """交互准备完成后立即关闭其目录 Session。"""

    def __init__(
        self,
        *,
        session: Session,
        container: ApplicationContainer,
        application: InteractionChatStreamApplication,
    ) -> None:
        self._session = session
        self._container = container
        self._application = application
        self._closed = False
        self._rollback_required = False

    def prepare(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation:
        if self._closed:
            raise RuntimeError("交互准备 Worker 已关闭。")
        try:
            preparation = self._application.prepare(command)
        except BaseException:
            self._rollback_required = True
            raise
        if preparation.event is not None and preparation.event.name == "error":
            self._rollback_required = True
        return preparation

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._rollback_required:
                self._session.rollback()
            else:
                self._session.commit()
        finally:
            try:
                self._container.close()
            finally:
                self._session.close()


class _SessionScopedStreamingConversationPersistenceWorker(
    StreamingConversationPersistenceWorkerPort
):
    """在 Composition 侧把同步 Conversation 应用能力收口到一个短 worker。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = build_conversation_access_service(session)
        self._writer = build_conversation_write_service(session)
        self._recent_reader = build_conversation_recent_message_read_service(session)
        self._closed = False

    def create_conversation(self, *, principal):  # noqa: ANN001
        return self._run(
            lambda: self._access.create(ConversationCreateCommand(principal=principal))
        )

    def resolve_conversation(self, *, principal, conversation_id):  # noqa: ANN001
        return self._run(
            lambda: self._access.resolve(
                ConversationResolveQuery(
                    principal=principal,
                    conversation_id=conversation_id,
                )
            )
        )

    def append_message(
        self,
        *,
        conversation_id,
        role: MessageRole,
        content: str,
    ) -> Message:
        return self._run(
            lambda: self._writer.append_message(
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
        )

    def read_recent_messages(
        self,
        *,
        conversation_id,
        through_sequence: int,
        limit: int,
    ) -> ConversationRecentMessageWindow:
        return self._run(
            lambda: self._recent_reader.read_recent_messages(
                conversation_id=conversation_id,
                through_sequence=through_sequence,
                limit=limit,
            )
        )

    def _run(self, operation):  # noqa: ANN001
        if self._closed:
            raise RuntimeError("持久化 worker 已关闭。")
        try:
            result = operation()
            self._session.commit()
            return result
        except BaseException:
            self._session.rollback()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._session.close()
