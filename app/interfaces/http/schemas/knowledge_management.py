"""知识库管理工作台的 HTTP 请求与响应 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.platform.knowledge.application.management_contracts import (
    KnowledgeManagementStatus,
)


class KnowledgeManagementDocumentListQuery(BaseModel):
    """文档管理列表的查询参数。"""

    search: str | None = Field(default=None, min_length=1)
    document_name: str | None = Field(default=None, min_length=1)
    policy_category: str | None = Field(default=None, min_length=1)
    status: list[KnowledgeManagementStatus] | None = None
    limit: int = Field(default=10, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class KnowledgeManagementRecentDocumentQuery(BaseModel):
    """概览页最近文档查询参数。"""

    search: str | None = Field(default=None, min_length=1)
    document_name: str | None = Field(default=None, min_length=1)
    policy_category: str | None = Field(default=None, min_length=1)
    status: list[KnowledgeManagementStatus] | None = None
    limit: int = Field(default=6, ge=1, le=20)


class KnowledgeManagementOverviewResponse(BaseModel):
    document_count: int
    chunk_count: int
    pending_count: int
    failed_count: int
    latest_updated_at: datetime | None


class KnowledgeManagementDocumentResponse(BaseModel):
    document_id: int
    policy_name: str
    policy_category: str
    responsible_department: str | None
    file_name: str | None
    file_type: str | None
    file_size_bytes: int | None
    version_id: int | None
    version_label: str | None
    processing_status: KnowledgeManagementStatus
    processing_progress: int | None
    publication_status: str | None
    parser_status: str | None
    section_count: int
    chunk_count: int
    updated_at: datetime | None
    updated_by: str | None
    error_message: str | None


class KnowledgeManagementDocumentListResponse(BaseModel):
    items: list[KnowledgeManagementDocumentResponse] = Field(default_factory=list)
    total_count: int = 0


class KnowledgeManagementCategoryListResponse(BaseModel):
    items: list[str] = Field(default_factory=list)


class KnowledgeManagementDocumentDetailResponse(KnowledgeManagementDocumentResponse):
    source_path: str | None
    page_count: int | None
    parse_method: str | None
    is_scanned: bool | None
    created_at: datetime | None


__all__ = [
    "KnowledgeManagementDocumentDetailResponse",
    "KnowledgeManagementDocumentListQuery",
    "KnowledgeManagementCategoryListResponse",
    "KnowledgeManagementRecentDocumentQuery",
    "KnowledgeManagementDocumentListResponse",
    "KnowledgeManagementDocumentResponse",
    "KnowledgeManagementOverviewResponse",
]
