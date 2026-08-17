"""知识库管理工作台 HTTP 接口。"""

import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.interfaces.http.assemblers.knowledge_management import (
    categories_response,
    detail_response,
    documents_response,
    management_query,
    overview_response,
    recent_management_query,
)
from app.interfaces.http.dependencies import get_knowledge_management_service
from app.interfaces.http.schemas.knowledge_management import (
    KnowledgeManagementCategoryListResponse,
    KnowledgeManagementDocumentDetailResponse,
    KnowledgeManagementDocumentListQuery,
    KnowledgeManagementDocumentListResponse,
    KnowledgeManagementOverviewResponse,
    KnowledgeManagementRecentDocumentQuery,
)
from app.modules.knowledge.application.management_service import KnowledgeManagementService

router = APIRouter()


@router.get("/management/overview", response_model=KnowledgeManagementOverviewResponse)
async def get_management_overview(
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> KnowledgeManagementOverviewResponse:
    return overview_response(service.get_overview())


@router.get(
    "/management/categories",
    response_model=KnowledgeManagementCategoryListResponse,
)
async def list_management_categories(
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> KnowledgeManagementCategoryListResponse:
    return categories_response(service.list_categories())


@router.get(
    "/management/documents",
    response_model=KnowledgeManagementDocumentListResponse,
)
async def list_management_documents(
    query: Annotated[KnowledgeManagementDocumentListQuery, Query()],
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> KnowledgeManagementDocumentListResponse:
    return documents_response(service.list_documents(management_query(query)))


@router.get(
    "/management/recent-documents",
    response_model=KnowledgeManagementDocumentListResponse,
)
async def list_recent_management_documents(
    query: Annotated[KnowledgeManagementRecentDocumentQuery, Query()],
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> KnowledgeManagementDocumentListResponse:
    return documents_response(
        service.list_recent_documents(recent_management_query(query))
    )


@router.get(
    "/management/documents/{document_id}",
    response_model=KnowledgeManagementDocumentDetailResponse,
)
async def get_management_document(
    document_id: int,
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> KnowledgeManagementDocumentDetailResponse:
    try:
        return detail_response(service.get_document(document_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.api_route("/management/documents/{document_id}/content", methods=["GET", "HEAD"])
async def get_management_document_content(
    document_id: int,
    service: KnowledgeManagementService = Depends(get_knowledge_management_service),
) -> FileResponse:
    """Return the registered original file without exposing its local path."""
    try:
        document = service.get_document(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not document.source_path:
        raise HTTPException(status_code=404, detail="该文档未保留可预览的原文件。")

    source_path = Path(document.source_path)
    if not source_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="原文件不可用，请重新上传该文档后再预览。",
        )

    media_type, _ = mimetypes.guess_type(source_path.name)
    return FileResponse(
        path=source_path,
        media_type=media_type or "application/octet-stream",
        filename=document.file_name or source_path.name,
        content_disposition_type="inline",
    )
