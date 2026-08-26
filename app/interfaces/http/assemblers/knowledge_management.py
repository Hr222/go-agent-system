"""知识库管理 HTTP Schema 与 Application 读模型之间的组装器。"""

from app.interfaces.http.schemas.knowledge_management import (
    KnowledgeManagementCategoryListResponse,
    KnowledgeManagementDocumentDetailResponse,
    KnowledgeManagementDocumentListQuery,
    KnowledgeManagementDocumentListResponse,
    KnowledgeManagementDocumentResponse,
    KnowledgeManagementOverviewResponse,
    KnowledgeManagementRecentDocumentQuery,
)
from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementDocument,
    KnowledgeManagementDocumentDetail,
    KnowledgeManagementDocumentPage,
    KnowledgeManagementOverviewResult,
    ListKnowledgeManagementDocumentsQuery,
)


def management_query(
    query: KnowledgeManagementDocumentListQuery,
) -> ListKnowledgeManagementDocumentsQuery:
    document_name = query.document_name or query.search
    return ListKnowledgeManagementDocumentsQuery(
        document_name=document_name,
        policy_category=query.policy_category,
        statuses=tuple(query.status or ()),
        limit=query.limit,
        offset=query.offset,
    )


def recent_management_query(
    query: KnowledgeManagementRecentDocumentQuery,
) -> ListKnowledgeManagementDocumentsQuery:
    document_name = query.document_name or query.search
    return ListKnowledgeManagementDocumentsQuery(
        document_name=document_name,
        policy_category=query.policy_category,
        statuses=tuple(query.status or ()),
        limit=query.limit,
    )


def categories_response(categories: list[str]) -> KnowledgeManagementCategoryListResponse:
    return KnowledgeManagementCategoryListResponse(items=categories)


def overview_response(
    result: KnowledgeManagementOverviewResult,
) -> KnowledgeManagementOverviewResponse:
    return KnowledgeManagementOverviewResponse(
        document_count=result.document_count,
        chunk_count=result.chunk_count,
        pending_count=result.pending_count,
        failed_count=result.failed_count,
        latest_updated_at=result.latest_updated_at,
    )


def document_response(
    document: KnowledgeManagementDocument,
) -> KnowledgeManagementDocumentResponse:
    return KnowledgeManagementDocumentResponse(
        document_id=document.document_id,
        policy_name=document.policy_name,
        policy_category=document.policy_category,
        responsible_department=document.responsible_department,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        version_id=document.version_id,
        version_label=document.version_label,
        processing_status=document.processing_status,
        processing_progress=document.processing_progress,
        publication_status=document.publication_status,
        parser_status=document.parser_status,
        section_count=document.section_count,
        chunk_count=document.chunk_count,
        updated_at=document.updated_at,
        updated_by=document.updated_by,
        error_message=document.error_message,
    )


def documents_response(
    documents: KnowledgeManagementDocumentPage,
) -> KnowledgeManagementDocumentListResponse:
    return KnowledgeManagementDocumentListResponse(
        items=[document_response(document) for document in documents.items],
        total_count=documents.total_count,
    )


def detail_response(
    document: KnowledgeManagementDocumentDetail,
) -> KnowledgeManagementDocumentDetailResponse:
    return KnowledgeManagementDocumentDetailResponse(
        **document_response(document).model_dump(),
        source_path=document.source_path,
        page_count=document.page_count,
        parse_method=document.parse_method,
        is_scanned=document.is_scanned,
        created_at=document.created_at,
    )
