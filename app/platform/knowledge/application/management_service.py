"""知识库管理工作台应用服务。"""

from __future__ import annotations

from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementDocumentDetail,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)
from app.platform.knowledge.ports.management_read_port import KnowledgeManagementReadPort


class KnowledgeManagementService:
    """管理读模型的应用服务，不承载 HTTP 或 ORM 细节。"""

    def __init__(self, read_port: KnowledgeManagementReadPort) -> None:
        self.read_port = read_port

    def get_overview(self) -> KnowledgeManagementOverviewResult:
        return self.read_port.get_overview()

    def list_categories(self) -> list[str]:
        return self.read_port.list_management_categories()

    def list_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage:
        self._validate_list_query(query)
        return self.read_port.list_management_documents(query)

    def list_recent_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage:
        """返回概览页所需的有限条最近文档，读取规则与全量列表保持一致。"""
        self._validate_list_query(query)
        return self.read_port.list_management_documents(query)

    @staticmethod
    def _validate_list_query(query: ListKnowledgeManagementDocumentsQuery) -> None:
        if query.limit < 1:
            raise ValueError("文档数量上限必须为正整数。")
        if query.offset < 0:
            raise ValueError("文档偏移量不能为负数。")

    def get_document(self, document_id: int) -> KnowledgeManagementDocumentDetail:
        if document_id < 1:
            raise ValueError("document_id 必须为正整数。")
        document = self.read_port.get_document(document_id)
        if document is None:
            raise LookupError(f"知识文档 {document_id} 不存在。")
        return document
