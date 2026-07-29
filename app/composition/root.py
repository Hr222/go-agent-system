from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy.orm import Session

from app.composition.agent import build_tender_structured_llm
from app.composition.ingestion import (
    build_ingestion_service,
    build_ingestion_use_case,
    build_pipeline,
    build_policy_candidate_scan_use_case,
    build_retry_ingestion_use_case,
    build_upload_service,
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
from app.composition.llm import build_chat_llm, build_streaming_chat_llm
from app.composition.online import (
    build_decision_service,
    build_policy_decision_application_service,
    build_rag_facade,
    build_rule_retrieval_service,
)
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
from app.modules.ingestion.application.ingestion_use_case import IngestionUseCase
from app.modules.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.modules.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.modules.ingestion.pipeline import PolicyIngestionService
from app.modules.knowledge import KnowledgeBaseQueryCapability, KnowledgePublicationService
from app.modules.knowledge.application.knowledge_base import KnowledgeBaseService
from app.modules.knowledge.application.management_service import KnowledgeManagementService
from app.modules.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.modules.llm.application.chat import ChatApplication
from app.modules.llm.application.streaming_chat import StreamingChatApplication
from app.modules.llm.contracts import ChatLlmPort, StreamingChatLlmPort, StructuredLlmPort
from app.modules.online.application.ask_knowledge import AskKnowledgeUseCase
from app.modules.online.application.data_acquisition import (
    ChecklistDataProviderRegistry,
    InlineChecklistDataProvider,
    PolicyDataAcquisitionService,
)
from app.modules.online.application.decision import (
    RuleDrivenChecklistDecisionService,
)
from app.modules.online.application.policy_decision import PolicyDecisionApplicationService
from app.modules.online.application.rag_facade import RagApplicationFacade
from app.modules.online.application.rule_retrieval import PolicyRuleRetrievalService
from app.modules.online.domain.checklist import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
    ChecklistScenarioRegistry,
    RuleDrivenChecklistPolicy,
)
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
        scenario_registry: ChecklistScenarioRegistry | None = None,
        checklist_policy: RuleDrivenChecklistPolicy | None = None,
        data_provider_registry: ChecklistDataProviderRegistry | None = None,
        answer_service: RagAnswerGenerator | None = None,
        tender_structured_llm: StructuredLlmPort | None = None,
        chat_llm: ChatLlmPort | None = None,
        streaming_chat_llm: StreamingChatLlmPort | None = None,
        openai_client_factory: OpenAICompatibleClientFactory | None = None,
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
        self._chat_llm = chat_llm
        self._chat_application: ChatApplication | None = None
        self._streaming_chat_llm = streaming_chat_llm
        self._streaming_chat_application: StreamingChatApplication | None = None
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
        self._policy_ingestion_service: PolicyIngestionService | None = None
        self._policy_candidate_scan_use_case: PolicyCandidateScanUseCase | None = None
        self._knowledge_base_service: KnowledgeBaseService | None = None
        self._knowledge_management_service: KnowledgeManagementService | None = None
        self._embedding_service: GiteeEmbeddingClient | None = None
        self._file_service: PolicyFileService | None = None
        self._ocr_service: PolicyOcrService | None = None

    def tender_structured_llm(self) -> StructuredLlmPort:
        """延迟组装招标书 Agent 使用的结构化 LLM 能力。"""

        if self._tender_structured_llm is None:
            self._tender_structured_llm = build_tender_structured_llm(
                self.openai_client_factory()
            )
        return self._tender_structured_llm

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

    def openai_client_factory(self) -> OpenAICompatibleClientFactory:
        """返回供 RAG 和 Agent 共享的 OpenAI-compatible Client Factory。"""

        if self._openai_client_factory is None:
            self._openai_client_factory = OpenAICompatibleClientFactory()
        return self._openai_client_factory

    def close(self) -> None:
        if self._openai_client_factory is not None:
            self._openai_client_factory.close()

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
