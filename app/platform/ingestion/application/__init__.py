"""入库用例。"""

from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase

__all__ = [
    "IngestionUseCase",
    "PolicyCandidateScanUseCase",
]
