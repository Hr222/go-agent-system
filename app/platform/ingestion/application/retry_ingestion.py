"""文档入库失败后的重试应用用例。"""

from __future__ import annotations

from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.contracts import PolicyPipelineRequest, PolicyPipelineResponse
from app.platform.ingestion.ports.retry_port import IngestionRetrySourcePort


class RetryIngestionUseCase:
    """通过来源端口恢复重试参数，再复用已有入库流水线。"""

    def __init__(
        self,
        ingestion_use_case: IngestionUseCase,
        source_port: IngestionRetrySourcePort,
    ) -> None:
        self.ingestion_use_case = ingestion_use_case
        self.source_port = source_port

    def retry(self, document_id: int) -> PolicyPipelineResponse:
        if document_id < 1:
            raise ValueError("document_id 必须为正整数。")

        source = self.source_port.get_retry_source(document_id)
        if source is None:
            raise LookupError(f"知识文档 {document_id} 没有可重试的入库来源。")

        return self.ingestion_use_case.ingest(
            PolicyPipelineRequest(
                source_path=source.source_path,
                policy_category=source.policy_category,
                responsible_department=source.responsible_department,
                version_label=source.version_label,
                target_document_id=source.target_document_id,
            )
        )

