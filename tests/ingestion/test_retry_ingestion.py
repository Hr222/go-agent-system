from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.platform.ingestion.contracts import PolicyPipelineResponse
from app.platform.ingestion.ports.retry_port import IngestionRetrySource


class FakeIngestionUseCase(IngestionUseCase):
    def __init__(self) -> None:
        self.request = None

    def ingest(self, request):  # noqa: ANN001
        self.request = request
        return PolicyPipelineResponse(mode="ingest", source_path=request.source_path)


class FakeRetrySourcePort:
    def get_retry_source(self, document_id: int):  # noqa: ANN001
        if document_id != 7:
            return None
        return IngestionRetrySource(
            source_path="D:/workspace/uploads/policy.pdf",
            policy_category="管理制度",
            responsible_department="采购部",
            version_label="2026版",
            target_document_id=7,
        )


def test_retry_ingestion_reuses_existing_ingest_use_case() -> None:
    ingestion = FakeIngestionUseCase()
    use_case = RetryIngestionUseCase(ingestion, FakeRetrySourcePort())

    response = use_case.retry(7)

    assert response.mode == "ingest"
    assert ingestion.request.source_path == "D:/workspace/uploads/policy.pdf"
    assert ingestion.request.target_document_id == 7

