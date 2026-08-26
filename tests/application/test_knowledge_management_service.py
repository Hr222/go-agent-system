from datetime import UTC, datetime

import pytest

from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementDocument,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)
from app.platform.knowledge.application.management_service import KnowledgeManagementService


class FakeManagementReadPort:
    def __init__(self) -> None:
        self.overview = KnowledgeManagementOverviewResult(
            document_count=2,
            chunk_count=12,
            pending_count=1,
            failed_count=0,
            latest_updated_at=datetime(2026, 7, 23, tzinfo=UTC),
        )
        self.documents = [
            KnowledgeManagementDocument(
                document_id=1,
                policy_name="采购管理制度",
                policy_category="管理制度",
                responsible_department=None,
                file_name="采购管理制度.pdf",
                file_type="pdf",
                file_size_bytes=None,
                version_id=3,
                version_label="2026版",
                processing_status="ready",
                processing_progress=100,
                publication_status="active",
                parser_status="parsed",
                section_count=2,
                chunk_count=12,
                updated_at=datetime(2026, 7, 23, tzinfo=UTC),
                updated_by=None,
                error_message=None,
            )
        ]
        self.queries: list[ListKnowledgeManagementDocumentsQuery] = []

    def list_management_categories(self) -> list[str]:
        return ["管理制度", "采购管理"]

    def get_overview(self) -> KnowledgeManagementOverviewResult:
        return self.overview

    def list_management_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage:
        self.queries.append(query)
        if query.statuses:
            assert query.statuses == ("ready",)
        return KnowledgeManagementDocumentPage(items=self.documents, total_count=1)

    def get_document(self, document_id: int):  # noqa: ANN001
        return self.documents[0] if document_id == 1 else None


def test_management_service_delegates_to_management_read_port() -> None:
    port = FakeManagementReadPort()
    service = KnowledgeManagementService(port)

    assert service.get_overview().document_count == 2
    documents = service.list_documents(
        ListKnowledgeManagementDocumentsQuery(statuses=("ready",))
    )

    assert documents.items[0].file_name == "采购管理制度.pdf"


def test_management_service_lists_categories() -> None:
    service = KnowledgeManagementService(FakeManagementReadPort())

    assert service.list_categories() == ["管理制度", "采购管理"]


def test_management_service_rejects_invalid_document_id() -> None:
    service = KnowledgeManagementService(FakeManagementReadPort())

    with pytest.raises(ValueError, match="document_id"):
        service.get_document(0)

    with pytest.raises(LookupError, match="不存在"):
        service.get_document(2)


def test_management_service_limits_recent_documents() -> None:
    port = FakeManagementReadPort()
    service = KnowledgeManagementService(port)

    service.list_recent_documents(ListKnowledgeManagementDocumentsQuery(limit=6))

    assert port.queries[-1].limit == 6
    assert port.queries[-1].offset == 0
