"""入库模块的 Composition Root，负责组装文件、OCR、向量和写入能力。"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.filesystem.policy_file_service import PolicyFileService
from app.infrastructure.filesystem.upload_service import PolicyUploadService
from app.infrastructure.ocr.tencent_ocr import PolicyOcrService
from app.platform.ingestion import PolicyIngestionService, PolicyPipelineService
from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase
from app.platform.ingestion.ports import IngestionRetrySourcePort
from app.platform.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.platform.llm.ports import TextEmbeddingPort


def build_pipeline(
    *,
    file_service: PolicyFileService,
    ocr_service: PolicyOcrService,
    write_capability: KnowledgeBaseWriteCapability | None = None,
    embedding_service: TextEmbeddingPort | None = None,
) -> PolicyPipelineService:
    return PolicyPipelineService(
        write_capability=write_capability,
        embedding_service=embedding_service,
        file_service=file_service,
        ocr_service=ocr_service,
    )


def build_upload_service(workspace_root: Path) -> PolicyUploadService:
    return PolicyUploadService(workspace_root)


def build_ingestion_service() -> PolicyIngestionService:
    return PolicyIngestionService()


def build_ingestion_use_case(pipeline: PolicyPipelineService) -> IngestionUseCase:
    return IngestionUseCase(pipeline)


def build_retry_ingestion_use_case(
    ingestion_use_case: IngestionUseCase,
    source_port: IngestionRetrySourcePort,
) -> RetryIngestionUseCase:
    return RetryIngestionUseCase(ingestion_use_case, source_port)


def build_policy_candidate_scan_use_case(
    scanner: PolicyIngestionService,
) -> PolicyCandidateScanUseCase:
    return PolicyCandidateScanUseCase(scanner)
