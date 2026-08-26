from fastapi import APIRouter, Depends, HTTPException

from app.interfaces.http.assemblers.publication import (
    publication_arguments,
    publication_response,
)
from app.interfaces.http.dependencies import get_knowledge_publication_service
from app.interfaces.http.schemas.publication import (
    KnowledgePublicationRequest,
    KnowledgePublicationResponse,
)
from app.platform.knowledge.application.publication_service import KnowledgePublicationService

router = APIRouter()


@router.post("/publication/activate", response_model=KnowledgePublicationResponse)
async def activate_knowledge_version(
    request: KnowledgePublicationRequest,
    service: KnowledgePublicationService = Depends(get_knowledge_publication_service),
) -> KnowledgePublicationResponse:
    """发布一个已入库版本，使其进入在线知识读模型。"""
    try:
        document_id, version_id = publication_arguments(request)
        result = service.publish(document_id=document_id, version_id=version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return publication_response(result)
