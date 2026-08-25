from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_knowledge_management_service
from app.main import create_app
from app.modules.knowledge.application.management_contracts import (
    KnowledgeManagementDocumentDetail,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)
from app.modules.knowledge.application.management_service import KnowledgeManagementService


class FakeManagementReadPort:
    def __init__(self, *, source_path: str | None = None) -> None:
        self.queries: list[ListKnowledgeManagementDocumentsQuery] = []
        self.source_path = source_path

    def get_overview(self) -> KnowledgeManagementOverviewResult:
        return KnowledgeManagementOverviewResult(
            document_count=0,
            chunk_count=0,
            pending_count=0,
            failed_count=0,
            latest_updated_at=None,
        )

    def list_management_categories(self) -> list[str]:
        return ["管理制度"]

    def list_management_documents(
        self,
        query: ListKnowledgeManagementDocumentsQuery,
    ) -> KnowledgeManagementDocumentPage:
        self.queries.append(query)
        return KnowledgeManagementDocumentPage(items=[self._document()], total_count=1)

    def get_document(self, document_id: int) -> KnowledgeManagementDocumentDetail | None:
        return self._document() if document_id == 1 else None

    def _document(self) -> KnowledgeManagementDocumentDetail:
        return KnowledgeManagementDocumentDetail(
            document_id=1,
            policy_name="资产评估师登记卡",
            policy_category="管理制度",
            responsible_department=None,
            file_name="资产评估师登记卡.pdf",
            file_type="pdf",
            file_size_bytes=None,
            version_id=1,
            version_label="v1.0",
            processing_status="ready",
            processing_progress=100,
            publication_status="active",
            parser_status="parsed",
            section_count=1,
            chunk_count=1,
            updated_at=None,
            updated_by=None,
            error_message=None,
            source_path=self.source_path,
            page_count=1,
            parse_method="ocr",
            is_scanned=True,
            created_at=None,
        )


def test_management_document_query_supports_empty_and_repeated_status_parameters() -> None:
    port = FakeManagementReadPort()
    application = create_app()
    application.dependency_overrides[get_knowledge_management_service] = lambda: (
        KnowledgeManagementService(port)
    )

    client = TestClient(application)
    assert client.get("/api/v1/kb/management/documents").status_code == 200
    response = client.get(
        "/api/v1/kb/management/documents",
        params=[
            ("document_name", "资产"),
            ("status", "ready"),
            ("status", "failed"),
            ("policy_category", "管理制度"),
        ],
    )

    assert response.status_code == 200
    assert port.queries[-1].document_name == "资产"
    assert port.queries[-1].statuses == ("ready", "failed")
    assert port.queries[-1].policy_category == "管理制度"

    application.dependency_overrides.clear()


def test_management_document_content_serves_registered_image_inline(tmp_path) -> None:
    source_path = tmp_path / "membership.jpg"
    source_path.write_bytes(b"image-content")
    application = create_app()
    application.dependency_overrides[get_knowledge_management_service] = lambda: (
        KnowledgeManagementService(FakeManagementReadPort(source_path=str(source_path)))
    )

    response = TestClient(application).get("/api/v1/kb/management/documents/1/content")

    assert response.status_code == 200
    assert response.content == b"image-content"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"].startswith("inline;")
    assert (
        TestClient(application).head("/api/v1/kb/management/documents/1/content").status_code == 200
    )
    application.dependency_overrides.clear()


def test_management_document_content_returns_not_found_when_source_is_missing() -> None:
    application = create_app()
    application.dependency_overrides[get_knowledge_management_service] = lambda: (
        KnowledgeManagementService(FakeManagementReadPort())
    )

    response = TestClient(application).get("/api/v1/kb/management/documents/1/content")

    assert response.status_code == 404
    application.dependency_overrides.clear()
