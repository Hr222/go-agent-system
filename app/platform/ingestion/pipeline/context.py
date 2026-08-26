from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.platform.ingestion.contracts import (
    ChunkSplitResult,
    CleanedTextResult,
    FormatNormalizationResult,
    IntakeValidationResult,
    OcrProcessResult,
    ParsedDocumentResult,
    ParsedTextResult,
    ParseRoutingResult,
    PersistenceResult,
    PolicyPipelineRequest,
    PolicyPipelineResponse,
    RegisteredFileInfo,
    SectionSplitResult,
)

PipelineMode = Literal["preview", "ingest"]


@dataclass(slots=True)
class PipelineContext:
    request: PolicyPipelineRequest
    mode: PipelineMode
    persist: bool
    response: PolicyPipelineResponse = field(init=False)
    policy_name_guess: str | None = None
    derived_version_label: str | None = None
    registered_file: RegisteredFileInfo | None = None
    validation: IntakeValidationResult | None = None
    normalization: FormatNormalizationResult | None = None
    parse_routing: ParseRoutingResult | None = None
    parsed_document: ParsedDocumentResult | None = None
    ocr_result: OcrProcessResult | None = None
    parsed_text: ParsedTextResult | None = None
    cleaned_text: CleanedTextResult | None = None
    section_result: SectionSplitResult | None = None
    chunk_result: ChunkSplitResult | None = None
    persistence: PersistenceResult | None = None
    stop_requested: bool = False

    def __post_init__(self) -> None:
        self.response = PolicyPipelineResponse(
            mode=self.mode,
            source_path=self.request.source_path,
            target_document_id=self.request.target_document_id,
            stages=[],
        )

    def stop(self) -> None:
        self.stop_requested = True
