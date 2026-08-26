"""知识能力模块的 Composition Root，负责组装端口、仓储和检索策略。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.llm.embedding_client import GiteeEmbeddingClient
from app.infrastructure.persistence.repositories.knowledge_publication_repository import (
    KnowledgePublicationRepository,
)
from app.infrastructure.persistence.repositories.knowledge_quality_audit_repository import (
    KnowledgeQualityAuditRepository,
)
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
from app.platform.knowledge.application.knowledge_base import KnowledgeBaseService
from app.platform.knowledge.application.management_service import KnowledgeManagementService
from app.platform.knowledge.application.publication_service import KnowledgePublicationService
from app.platform.knowledge.application.quality_audit import KnowledgeQualityAuditService
from app.platform.knowledge.application.query_capability import KnowledgeBaseQueryCapability
from app.platform.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.platform.knowledge.retrieval import HybridRetrievalPipeline, KnowledgeRetrievalService
from app.platform.knowledge.retrieval.contracts import QueryEmbeddingService
from app.platform.knowledge.retrieval.vector_search import (
    VectorSearchStrategyName,
    build_vector_search_strategy,
)


def build_persistence_gateway(session: Session) -> PolicyPersistenceGateway:
    return PolicyPersistenceGateway(session)


def build_read_repository(
    gateway: PolicyPersistenceGateway,
    *,
    embedding_service: QueryEmbeddingService,
) -> KnowledgeReadRepository:
    return KnowledgeReadRepository(gateway, embedding_service=embedding_service)


def build_write_repository(gateway: PolicyPersistenceGateway) -> KnowledgeWriteRepository:
    return KnowledgeWriteRepository(gateway)


def build_quality_audit_service(session: Session) -> KnowledgeQualityAuditService:
    """组装 E1/E2 只读知识库审计服务。"""

    return KnowledgeQualityAuditService(KnowledgeQualityAuditRepository(session))


def build_runtime_quality_audit_service() -> tuple[Session, KnowledgeQualityAuditService]:
    """为审计脚本创建独立会话与只读审计服务。"""

    session = SessionLocal()
    return session, build_quality_audit_service(session)


def build_write_capability(
    write_repository: KnowledgeWriteRepository,
) -> KnowledgeBaseWriteCapability:
    return KnowledgeBaseWriteCapability(write_repository)


def build_query_capability(
    read_repository: KnowledgeReadRepository,
) -> KnowledgeBaseQueryCapability:
    return KnowledgeBaseQueryCapability(read_repository)


def build_publication_service(session: Session) -> KnowledgePublicationService:
    return KnowledgePublicationService(KnowledgePublicationRepository(session))


def build_knowledge_base_service(read_repository: KnowledgeReadRepository) -> KnowledgeBaseService:
    return KnowledgeBaseService(read_port=read_repository)


def build_knowledge_management_service(
    read_repository: KnowledgeReadRepository,
) -> KnowledgeManagementService:
    return KnowledgeManagementService(read_port=read_repository)


def build_benchmark_retrieval_service(
    strategy_name: VectorSearchStrategyName,
) -> tuple[Session, KnowledgeRetrievalService]:
    """为评测脚本组装独立的检索服务和会话。"""

    session = SessionLocal()
    repository = PolicyPersistenceGateway(session)
    pipeline = HybridRetrievalPipeline(
        repository=repository,
        embedding_service=GiteeEmbeddingClient(),
        vector_search_strategy=build_vector_search_strategy(strategy_name),
    )
    return session, KnowledgeRetrievalService(repository, pipeline=pipeline)
