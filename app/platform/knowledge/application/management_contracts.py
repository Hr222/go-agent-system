"""知识库管理工作台使用的应用层读模型契约。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

KnowledgeManagementStatus = Literal["ready", "processing", "failed"]


@dataclass(slots=True, frozen=True)
class KnowledgeManagementOverviewResult:
    """知识库管理概览，不暴露数据库聚合对象。"""

    document_count: int
    chunk_count: int
    pending_count: int
    failed_count: int
    latest_updated_at: datetime | None


@dataclass(slots=True, frozen=True)
class ListKnowledgeManagementDocumentsQuery:
    document_name: str | None = None
    policy_category: str | None = None
    statuses: tuple[KnowledgeManagementStatus, ...] = ()
    limit: int = 10
    offset: int = 0


@dataclass(slots=True, frozen=True)
class KnowledgeManagementDocumentPage:
    items: list[KnowledgeManagementDocument]
    total_count: int


@dataclass(slots=True, frozen=True)
class KnowledgeManagementDocument:
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


@dataclass(slots=True, frozen=True)
class KnowledgeManagementDocumentDetail(KnowledgeManagementDocument):
    source_path: str | None
    page_count: int | None
    parse_method: str | None
    is_scanned: bool | None
    created_at: datetime | None
