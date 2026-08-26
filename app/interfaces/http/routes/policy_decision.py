from fastapi import APIRouter, Depends, HTTPException

from app.business.online.application.policy_decision import PolicyDecisionApplicationService
from app.interfaces.http.assemblers.policy_decision import decision_command, decision_response
from app.interfaces.http.dependencies import get_policy_decision_application_service
from app.interfaces.http.schemas.policy_decision import (
    PolicyDecisionRequest,
    PolicyDecisionResponse,
)
from app.shared.exceptions import KnowledgeBaseSchemaUnavailableError, UpstreamServiceError

router = APIRouter()


@router.post(
    "/policy-decisions/court-evaluation-materials/review",
    response_model=PolicyDecisionResponse,
)
async def review_court_evaluation_materials(
    request: PolicyDecisionRequest,
    service: PolicyDecisionApplicationService = Depends(get_policy_decision_application_service),
) -> PolicyDecisionResponse:
    """通过在线决策应用层暴露当前材料核验能力。"""
    return await _review_policy_decision(request, service)


@router.post(
    "/policy-decisions/{scenario_code}/review",
    response_model=PolicyDecisionResponse,
)
async def review_policy_decision(
    scenario_code: str,
    request: PolicyDecisionRequest,
    service: PolicyDecisionApplicationService = Depends(get_policy_decision_application_service),
) -> PolicyDecisionResponse:
    """通过场景编码复用统一的规则决策链路。"""
    return await _review_policy_decision(request, service, scenario_code=scenario_code)


async def _review_policy_decision(
    request: PolicyDecisionRequest,
    service: PolicyDecisionApplicationService,
    *,
    scenario_code: str | None = None,
) -> PolicyDecisionResponse:
    """统一处理兼容入口与通用入口的异常映射。"""
    try:
        return decision_response(
            service.review(decision_command(request, scenario_code=scenario_code))
        )
    except KnowledgeBaseSchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
