from __future__ import annotations

from app.infrastructure.persistence.repositories.policy_persistence_gateway import (
    PolicyPersistenceGateway,
)
from app.infrastructure.persistence.schema_health import translate_missing_kb_schema_errors
from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementDocumentDetail,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)
from app.platform.knowledge.ports.management_read_port import KnowledgeManagementReadPort
from app.platform.knowledge.ports.read_port import (
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeReadPort,
)
from app.platform.knowledge.retrieval import KnowledgeRetrievalService
from app.platform.knowledge.retrieval.contracts import QueryEmbeddingService


class KnowledgeReadRepository(KnowledgeReadPort, KnowledgeManagementReadPort):
    """PostgreSQL/pgvector 读仓储适配器。

    现阶段复用已经稳定的混合检索实现，外部只看到知识端口，不再直接拿到旧仓储。
    """

    def __init__(
        self,
        gateway: PolicyPersistenceGateway,
        *,
        embedding_service: QueryEmbeddingService | None = None,
    ) -> None:
        self.gateway = gateway
        self.retrieval_service = KnowledgeRetrievalService(
            gateway,
            embedding_service=embedding_service,
        )

    @translate_missing_kb_schema_errors
    def search(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        return self.retrieval_service.search(query)

    @translate_missing_kb_schema_errors
    def list_documents(
        self,
        *,
        search: str | None = None,
        policy_category: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeDocument]:
        return [
            KnowledgeDocument(
                document_id=item.document_id,
                policy_name=item.policy_name,
                policy_category=item.policy_category,
                responsible_department=item.responsible_department,
                latest_version_id=item.latest_version_id,
                latest_version_label=item.latest_version_label,
            )
            for item in self.gateway.list_documents(
                search=search,
                policy_category=policy_category,
                limit=limit,
            )
        ]

    @translate_missing_kb_schema_errors
    def get_overview(self) -> KnowledgeManagementOverviewResult:
        return self.gateway.get_management_overview()

    @translate_missing_kb_schema_errors
    def list_management_categories(self) -> list[str]:
        return self.gateway.list_management_categories()

    @translate_missing_kb_schema_errors
    def list_management_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage:
        return self.gateway.list_management_documents(query)

    @translate_missing_kb_schema_errors
    def get_document(
        self,
        document_id: int,
    ) -> KnowledgeManagementDocumentDetail | None:
        return self.gateway.get_management_document(document_id)
