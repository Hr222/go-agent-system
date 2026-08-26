"""知识库管理工作台的读端口。"""

from __future__ import annotations

from typing import Protocol

from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementDocumentDetail,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)


class KnowledgeManagementReadPort(Protocol):
    """为管理工作台提供独立读模型的端口。"""

    def get_overview(self) -> KnowledgeManagementOverviewResult: ...

    def list_management_categories(self) -> list[str]: ...

    def list_management_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage: ...

    def get_document(self, document_id: int) -> KnowledgeManagementDocumentDetail | None: ...
