from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

PackageType = Literal["single_volume", "multi_volume", "uncertain"]
AnalysisStatus = Literal["completed", "needs_review"]
RequirementKind = Literal[
    "composition",
    "section",
    "form",
    "table",
    "attachment",
    "submission",
    "placeholder",
    "risk",
]


class TenderSourceEvidence(BaseModel):
    """招标文件中可供结果回溯的位置证据。"""

    evidence_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    page_no: int | None = Field(default=None, ge=1)
    section_title: str | None = None


class TenderRequirement(BaseModel):
    """从招标文件明确提取的一项投标要求。"""

    requirement_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    kind: RequirementKind
    required: bool = True
    output_slug: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TenderOutputPlan(BaseModel):
    """一个投标骨架文件的输出计划。"""

    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    document_label: str = Field(min_length=1)
    purpose: str | None = None
    section_titles: list[str] = Field(default_factory=list)
    requirement_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_start_block_id: str | None = Field(default=None, min_length=1)
    source_end_block_id: str | None = Field(default=None, min_length=1)


class TenderAnalysis(BaseModel):
    """Tender Agent 对一次招标文件的结构化分析结果。"""

    status: AnalysisStatus
    package_type: PackageType
    summary: str = Field(min_length=1)
    format_start_block_id: str | None = Field(default=None, min_length=1)
    format_end_block_id: str | None = Field(default=None, min_length=1)
    key_requirements: list[TenderRequirement] = Field(default_factory=list)
    outputs: list[TenderOutputPlan] = Field(default_factory=list)
    evidence: list[TenderSourceEvidence] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class TenderBoundaryVerification(BaseModel):
    """单卷格式区域边界的第二阶段复核结果。"""

    should_adjust: bool
    reason: str = Field(min_length=1)
    new_start_block_id: str | None = Field(default=None, min_length=1)
    new_end_block_id: str | None = Field(default=None, min_length=1)


@dataclass(slots=True, frozen=True)
class TenderDocumentBlock:
    """DOCX 中可以被引用和复制的段落或表格块。"""

    block_id: str
    kind: Literal["paragraph", "table"]
    text: str
    table_rows: tuple[tuple[str, ...], ...] = ()
    style_name: str | None = None
    heading_level: int | None = None
    order: int = 0
    heading_path: tuple[str, ...] = ()
    table_header: tuple[str, ...] = ()
    is_template: bool = False
    paragraph_number: int | None = None


@dataclass(slots=True, frozen=True)
class TenderDocument:
    """请求级招标文档，保留原始字节以供渲染器读取模板内容。"""

    file_name: str
    content: bytes
    blocks: tuple[TenderDocumentBlock, ...]
    source_text: str
    resource_stats: "TenderDocumentResourceStats | None" = None

    def block_map(self) -> dict[str, TenderDocumentBlock]:
        return {block.block_id: block for block in self.blocks}


@dataclass(slots=True, frozen=True)
class TenderDocumentResourceStats:
    """DOCX 压缩包的请求级资源统计，不保存压缩包内容。"""

    compressed_bytes: int
    uncompressed_bytes: int
    file_count: int
    max_compression_ratio: float


@dataclass(slots=True, frozen=True)
class TenderAnalysisBudget:
    """分块、归并和请求级调用预算。"""

    chunk_threshold_bytes: int = 4 * 1024 * 1024
    chunk_input_chars: int = 8_000
    merge_input_chars: int = 18_000
    max_output_chars: int = 16_000
    max_chunks: int = 128
    max_merge_items: int = 8
    max_llm_calls: int = 160
    max_retries: int = 1
    max_total_seconds: float = 300.0


@dataclass(slots=True, frozen=True)
class TenderChunk:
    """一个可独立提交给局部提取器的证据分块。"""

    chunk_id: str
    sequence: int
    text: str
    evidence_ids: tuple[str, ...]
    heading_path: tuple[str, ...] = ()
    table_header: tuple[str, ...] = ()
    estimated_tokens: int = 0


@dataclass(slots=True, frozen=True)
class TenderChunkPlan:
    """一次请求的有序分块计划。"""

    chunks: tuple[TenderChunk, ...]
    source_block_ids: tuple[str, ...]


class TenderChunkOutputCandidate(BaseModel):
    """局部结果中的投标分线候选，不代表最终单卷/多卷结论。"""

    label: str = Field(min_length=1)
    purpose: str | None = None
    section_titles: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class TenderChunkAnalysis(BaseModel):
    """一个分块的紧凑、有证据局部分析结果。"""

    chunk_id: str = Field(min_length=1)
    requirements: list[TenderRequirement] = Field(default_factory=list)
    output_candidates: list[TenderChunkOutputCandidate] = Field(default_factory=list)
    submission_rules: list[str] = Field(default_factory=list)
    evidence: list[TenderSourceEvidence] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    coverage_complete: bool = True


@dataclass(slots=True, frozen=True)
class TenderMergeBatch:
    """归并器的一次有界输入批次。"""

    batch_id: str
    level: int
    items: tuple[TenderChunkAnalysis | TenderAnalysis, ...]
    evidence_ids: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class TenderGenerateSkeletonCommand:
    """Tender Agent V1 的一次同步调用输入。"""

    file_name: str
    content: bytes
    user_focus: str | None = None


@dataclass(slots=True, frozen=True)
class GeneratedTenderArtifact:
    """一次请求生成的可下载文件。"""

    file_name: str
    media_type: str
    content: bytes


@dataclass(slots=True, frozen=True)
class TenderGenerateSkeletonResult:
    """Tender Agent V1 的一次同步调用结果。"""

    analysis: TenderAnalysis
    artifacts: tuple[GeneratedTenderArtifact, ...]
    model: str
    prompt_version: str


@dataclass(slots=True, frozen=True)
class TenderExtractFormatSectionCommand:
    """Request to copy a confirmed format range from a source DOCX."""

    file_name: str
    content: bytes
    start_block_id: str
    end_block_id: str
    output_name: str | None = None


@dataclass(slots=True, frozen=True)
class TenderExtractFormatSectionResult:
    """Deterministically extracted format section and its source range."""

    artifact: GeneratedTenderArtifact
    start_block_id: str
    end_block_id: str
    block_count: int
    table_count: int


@dataclass(slots=True, frozen=True)
class TenderBoundaryContextBlock:
    """A source block returned around a candidate extraction boundary."""

    block_id: str
    kind: str
    text: str
    order: int
    position: int
    heading_path: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class TenderVerifyExtractionBoundaryCommand:
    """Request to inspect source context around candidate boundary blocks."""

    file_name: str
    content: bytes
    start_block_id: str
    end_block_id: str
    context_radius: int = 3


@dataclass(slots=True, frozen=True)
class TenderVerifyExtractionBoundaryResult:
    """Structured source context for an Agent boundary decision."""

    start_block_id: str
    end_block_id: str
    start_position: int
    end_position: int
    context: tuple[TenderBoundaryContextBlock, ...]


@dataclass(slots=True, frozen=True)
class TenderFillContentCommand:
    """V2 资料填充能力的预留输入契约。"""

    analysis: TenderAnalysis
    artifacts: tuple[GeneratedTenderArtifact, ...]
    material_refs: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class TenderFilledArtifact:
    """V2 资料填充能力的预留文件结果。"""

    file_name: str
    media_type: str
    content: bytes
    missing_materials: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    citation_refs: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class TenderFillContentResult:
    """V2 资料填充能力的预留结果契约。"""

    artifacts: tuple[TenderFilledArtifact, ...]
    missing_materials: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
