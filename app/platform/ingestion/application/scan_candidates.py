from __future__ import annotations

from app.platform.ingestion.contracts import PolicyScanRequest, PolicyScanResponse
from app.platform.ingestion.pipeline.scan_service import PolicyIngestionService


class PolicyCandidateScanUseCase:
    """扫描待入库候选文件的应用用例。"""

    def __init__(self, scanner: PolicyIngestionService) -> None:
        self.scanner = scanner

    def scan(self, request: PolicyScanRequest) -> PolicyScanResponse:
        return self.scanner.scan_candidates(request)
