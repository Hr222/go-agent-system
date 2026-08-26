from fastapi import APIRouter, Depends, HTTPException

from app.interfaces.http.assemblers.policy_ingestion import scan_command, scan_response
from app.interfaces.http.dependencies import get_policy_candidate_scan_use_case
from app.interfaces.http.schemas.policy_ingestion import PolicyScanRequest, PolicyScanResponse
from app.platform.ingestion.application.scan_candidates import PolicyCandidateScanUseCase

router = APIRouter()


@router.post("/policy-ingestion/scan", response_model=PolicyScanResponse)
async def scan_policy_candidates(
    request: PolicyScanRequest,
    use_case: PolicyCandidateScanUseCase = Depends(get_policy_candidate_scan_use_case),
) -> PolicyScanResponse:
    """通过统一依赖入口执行候选制度文件扫描。"""
    try:
        return scan_response(use_case.scan(scan_command(request)))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
