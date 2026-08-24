from functools import lru_cache

from fastapi import Depends

from app.composition import ApplicationContainer, get_db_session
from app.modules.conversation.application import (
    ConversationAccessService,
    ConversationHistoryReadService,
    ConversationListReadService,
    ConversationManagementService,
    ConversationTopicSummaryUpdateService,
)
from app.modules.dialogue.application import (
    InMemoryPendingAgentInvocationStore,
)
from app.modules.ingestion.application.ingestion_use_case import IngestionUseCase
from app.modules.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.modules.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.modules.ingestion.ports import UploadStoragePort
from app.modules.interaction.application.chat_stream import InteractionChatStreamApplication
from app.modules.interaction.application.gateway import (
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.modules.interaction.ports.proposal_store import PendingProposalStorePort
from app.modules.knowledge.application.knowledge_base import KnowledgeBaseService
from app.modules.knowledge.application.management_service import KnowledgeManagementService
from app.modules.knowledge.application.publication_service import KnowledgePublicationService
from app.modules.online.application.ask_knowledge import AskKnowledgeUseCase
from app.modules.online.application.policy_decision import PolicyDecisionApplicationService
from app.shared.config import settings


@lru_cache(maxsize=1)
def get_stateless_application_container() -> ApplicationContainer:
    """Provide one process-wide container for stateless capabilities."""
    return ApplicationContainer()


def get_attachment_storage(
    container: ApplicationContainer = Depends(get_stateless_application_container),
):
    """Provide the process-wide attachment staging service."""
    return container.attachment_storage()


def get_application_container(
    session=Depends(get_db_session),  # noqa: ANN001
    attachment_storage=Depends(get_attachment_storage),  # noqa: ANN001
) -> ApplicationContainer:
    """为需要数据库能力的请求提供统一装配容器。"""
    return ApplicationContainer(session, attachment_storage=attachment_storage)


def get_conversation_access_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> ConversationAccessService:
    """Provide the owner-scoped Conversation admission service for one request."""

    return container.conversation_access()


def get_conversation_history_read_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> ConversationHistoryReadService:
    """Provide the Conversation application service for read-only history queries."""

    return container.conversation_history_read()


def get_conversation_list_read_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> ConversationListReadService:
    """Provide the owner-scoped Conversation summary read service."""

    return container.conversation_list_read()


def get_conversation_topic_summary_update_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> ConversationTopicSummaryUpdateService:
    """提供 owner-scoped 话题概括修改服务。"""

    return container.conversation_topic_summary_update()


def get_conversation_management_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> ConversationManagementService:
    return container.conversation_management()


@lru_cache(maxsize=1)
def get_interaction_proposal_store() -> PendingProposalStorePort:
    """确认跨 HTTP 请求时共享短 TTL、一次消费的服务端状态。"""

    return InMemoryPendingProposalStore(
        ttl_seconds=settings.interaction_proposal_ttl_seconds,
    )


def get_intent_interaction_gateway(
    container: ApplicationContainer = Depends(get_application_container),
    proposal_store: PendingProposalStorePort = Depends(get_interaction_proposal_store),
) -> IntentInteractionGateway:
    return container.intent_interaction_gateway(proposal_store)


@lru_cache(maxsize=1)
def get_pending_agent_invocation_store() -> InMemoryPendingAgentInvocationStore:
    return InMemoryPendingAgentInvocationStore(
        ttl_seconds=settings.interaction_proposal_ttl_seconds,
    )


def get_interaction_chat_stream_application(
    container: ApplicationContainer = Depends(get_application_container),
    proposal_store: PendingProposalStorePort = Depends(get_interaction_proposal_store),
    pending_agent_invocations: InMemoryPendingAgentInvocationStore = Depends(
        get_pending_agent_invocation_store
    ),
) -> InteractionChatStreamApplication:
    return container.interaction_chat_stream_application(
        proposal_store,
        pending_agent_invocations,
    )


@lru_cache(maxsize=1)
def get_stateless_application_container_legacy() -> ApplicationContainer:
    """为纯内存或文件系统能力提供无会话容器。"""
    return ApplicationContainer()


def get_ask_knowledge_use_case(
    container: ApplicationContainer = Depends(get_application_container),
) -> AskKnowledgeUseCase:
    """提供在线知识问答应用用例。"""
    return container.ask_knowledge_use_case()


def get_policy_decision_application_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> PolicyDecisionApplicationService:
    """提供规则决策应用用例。"""
    return container.policy_decision_application_service()


def get_knowledge_publication_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> KnowledgePublicationService:
    """提供知识版本发布用例。"""
    return container.knowledge_publication_service()


def get_ingestion_preview_use_case(
    container: ApplicationContainer = Depends(get_stateless_application_container),
) -> IngestionUseCase:
    """提供文档入库预览用例。"""
    return container.ingestion_preview_use_case()


def get_ingestion_use_case(
    container: ApplicationContainer = Depends(get_application_container),
) -> IngestionUseCase:
    """提供文档入库用例。"""
    return container.ingestion_use_case()


def get_retry_ingestion_use_case(
    container: ApplicationContainer = Depends(get_application_container),
) -> RetryIngestionUseCase:
    """提供文档入库重试用例。"""
    return container.retry_ingestion_use_case()


def get_policy_upload_service(
    container: ApplicationContainer = Depends(get_stateless_application_container),
) -> UploadStoragePort:
    """提供上传暂存服务。"""
    return container.policy_upload_service()


def get_attachment_storage_legacy(
    container: ApplicationContainer = Depends(get_stateless_application_container_legacy),
):
    """提供通用附件暂存服务。"""
    return container.attachment_storage()


def get_policy_candidate_scan_use_case(
    container: ApplicationContainer = Depends(get_stateless_application_container),
) -> PolicyCandidateScanUseCase:
    """提供候选文件扫描用例。"""
    return container.policy_candidate_scan_use_case()


def get_knowledge_base_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> KnowledgeBaseService:
    """提供知识库轻量管理服务。"""
    return container.knowledge_base_service()


def get_knowledge_management_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> KnowledgeManagementService:
    """提供知识库管理读模型应用服务。"""
    return container.knowledge_management_service()
