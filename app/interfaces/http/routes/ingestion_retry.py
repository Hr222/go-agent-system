"""文档入库重试 HTTP 接口。"""

from fastapi import APIRouter, Depends, HTTPException

from app.interfaces.http.assemblers.policy_pipeline import pipeline_response
from app.interfaces.http.dependencies import get_retry_ingestion_use_case
from app.interfaces.http.schemas import PolicyPipelineResponse
from app.platform.ingestion.application.retry_ingestion import RetryIngestionUseCase
from app.shared.exceptions import KnowledgeBaseSchemaUnavailableError

router = APIRouter()


@router.post(
    "/documents/{document_id}/retry",
    response_model=PolicyPipelineResponse,
)
async def retry_document_ingestion(
    document_id: int,
    use_case: RetryIngestionUseCase = Depends(get_retry_ingestion_use_case),
) -> PolicyPipelineResponse:
    try:
        return pipeline_response(use_case.retry(document_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KnowledgeBaseSchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

