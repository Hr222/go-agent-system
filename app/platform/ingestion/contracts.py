from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PipelineStageName = Literal[
    "file_registration",
    "intake_validation",
    "format_normalization",
    "parse_routing",
    "document_parsing",
    "ocr_processing",
    "text_assembly",
    "ingest_guard",
    "text_cleaning",
    "section_splitting",
    "chunk_splitting",
    "embedding_generation",
    "chunk_persistence",
    "document_persistence",
]
PipelineStatus = Literal["pending", "skipped", "success", "failed"]
ParserStatus = Literal["parsed", "failed"]
DocumentFileType = Literal["docx", "pdf", "image"]
ParseMethod = Literal["direct", "ocr", "mixed"]
BlockType = Literal["text", "table", "image", "page_break"]
BlockSource = Literal["direct", "ocr", "mixed"]


class PolicyPipelineRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    policy_category: str = Field(default="管理制度", min_length=1)
    responsible_department: str | None = None
    version_label: str | None = None
    target_document_id: int | None = Field(default=None, ge=1)


class PipelineStageResult(BaseModel):
    stage: PipelineStageName
    status: PipelineStatus
    message: str


class PersistenceResult(BaseModel):
    persisted: bool
    document_id: int | None = None
    version_id: int | None = None
    version_seq: int | None = None
    version_label: str | None = None
    section_count: int = 0
    chunk_count: int = 0
    message: str


class SectionSplitItem(BaseModel):
    section_no: str | None = None
    section_title: str | None = None
    section_level: int
    section_path: str | None = None
    section_order: int
    section_text: str
    page_start: int | None = None
    page_end: int | None = None
    source_block_start: int | None = None
    source_block_end: int | None = None


class SectionSplitResult(BaseModel):
    total_sections: int
    strategy: str
    sections: list[SectionSplitItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ChunkItem(BaseModel):
    chunk_index: int
    section_order: int
    section_title: str | None = None
    section_path: str | None = None
    section_id: int | None = None
    page_no: int | None = None
    chunk_text: str
    chunk_in_section: int
    chunk_start_offset: int
    chunk_end_offset: int
    char_count: int
    source_block_start: int | None = None
    source_block_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class ChunkSampleItem(BaseModel):
    section_title: str | None = None
    section_path: str | None = None
    chunk_preview: str
    char_count: int


class ChunkSplitResult(BaseModel):
    total_chunks: int
    strategy: str
    notes: list[str] = Field(default_factory=list)
    chunks: list[ChunkItem] = Field(default_factory=list)
    sample_chunks: list[ChunkSampleItem] = Field(default_factory=list)


class RegisteredFileInfo(BaseModel):
    source_path: str
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    source_modified_at: datetime


class IntakeValidationResult(BaseModel):
    is_allowed: bool
    detected_file_kind: str
    needs_normalization: bool
    recommended_parse_method: str
    warnings: list[str]


class FormatNormalizationResult(BaseModel):
    status: PipelineStatus
    source_path: str
    normalized_path: str
    output_extension: str
    converter: str
    message: str


class ParseRoutingResult(BaseModel):
    parser_name: str
    parse_method: str
    suspected_scanned_pdf: bool
    notes: list[str]


class ParsedBlock(BaseModel):
    block_id: str
    order: int
    page_no: int | None = None
    block_type: BlockType
    source: BlockSource
    text: str | None = None
    layout_hint: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssembledLine(BaseModel):
    text: str
    page_no: int | None = None
    source_block_order: int | None = None


class ParsedDocumentResult(BaseModel):
    parser_status: ParserStatus
    source_path: str
    file_type: DocumentFileType
    suspected_scanned: bool = False
    blocks: list[ParsedBlock]
    notes: list[str]


class OcrProcessResult(BaseModel):
    applied: bool
    parse_method: ParseMethod
    blocks: list[ParsedBlock]
    notes: list[str]
    failed_blocks: int = 0


class ParsedTextResult(BaseModel):
    parser_status: ParserStatus
    source_path: str
    parse_method: ParseMethod
    raw_text: str
    page_count: int | None = None
    suspected_scanned: bool = False
    lines: list[AssembledLine] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    title_candidates: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CleanedTextResult(BaseModel):
    clean_text: str
    page_count: int | None = None
    lines: list[AssembledLine] = Field(default_factory=list)
    removed_noise_examples: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PolicyPipelineResponse(BaseModel):
    mode: Literal["preview", "ingest"]
    source_path: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stages: list[PipelineStageResult] = Field(default_factory=list)
    policy_name_guess: str | None = None
    derived_version_label: str | None = None
    target_document_id: int | None = None
    registered_file: RegisteredFileInfo | None = None
    validation: IntakeValidationResult | None = None
    normalization: FormatNormalizationResult | None = None
    parse_routing: ParseRoutingResult | None = None
    parsed_text: ParsedTextResult | None = None
    cleaned_text: CleanedTextResult | None = None
    section_result: SectionSplitResult | None = None
    chunk_result: ChunkSplitResult | None = None
    persistence: PersistenceResult | None = None


class PolicyCandidateItem(BaseModel):
    source_path: str
    relative_path: str
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    recommended_action: str
    parse_method: str
    suspected_scanned: bool
    policy_name_guess: str
    include_reason: str | None = None
    exclude_reason: str | None = None


class PolicyScanStats(BaseModel):
    total_files: int
    included_files: int
    excluded_files: int
    review_files: int
    by_extension: dict[str, int]


class PolicyScanRequest(BaseModel):
    source_root: str = Field(..., min_length=1)
    limit: int = Field(default=50, ge=1, le=500)


class PolicyScanResponse(BaseModel):
    source_root: str
    scanned_at: datetime
    stats: PolicyScanStats
    candidates: list[PolicyCandidateItem]
