from __future__ import annotations

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
    PipelineStageName,
    PipelineStageResult,
    PipelineStatus,
    PolicyPipelineResponse,
    RegisteredFileInfo,
    SectionSplitResult,
)
from app.platform.ingestion.pipeline.context import PipelineContext


class PipelineResponseBuilder:
    def __init__(self, context: PipelineContext) -> None:
        self.context = context

    def set_policy_identity(
        self,
        *,
        policy_name_guess: str | None,
        derived_version_label: str | None,
    ) -> None:
        self.context.policy_name_guess = policy_name_guess
        self.context.derived_version_label = derived_version_label
        self.context.response.policy_name_guess = policy_name_guess
        self.context.response.derived_version_label = derived_version_label

    def set_registered_file(self, registered_file: RegisteredFileInfo) -> None:
        self.context.registered_file = registered_file
        self.context.response.registered_file = registered_file

    def set_validation(self, validation: IntakeValidationResult) -> None:
        self.context.validation = validation
        self.context.response.validation = validation

    def set_normalization(self, normalization: FormatNormalizationResult) -> None:
        self.context.normalization = normalization
        self.context.response.normalization = normalization

    def set_parse_routing(self, parse_routing: ParseRoutingResult) -> None:
        self.context.parse_routing = parse_routing
        self.context.response.parse_routing = parse_routing

    def set_parsed_document(self, parsed_document: ParsedDocumentResult) -> None:
        self.context.parsed_document = parsed_document

    def set_ocr_result(self, ocr_result: OcrProcessResult) -> None:
        self.context.ocr_result = ocr_result

    def set_parsed_text(self, parsed_text: ParsedTextResult) -> None:
        self.context.parsed_text = parsed_text
        self.context.response.parsed_text = parsed_text

    def set_cleaned_text(self, cleaned_text: CleanedTextResult) -> None:
        self.context.cleaned_text = cleaned_text
        self.context.response.cleaned_text = cleaned_text

    def set_section_result(self, section_result: SectionSplitResult) -> None:
        self.context.section_result = section_result
        self.context.response.section_result = section_result

    def set_chunk_result(
        self,
        chunk_result: ChunkSplitResult,
        *,
        include_chunks: bool = False,
    ) -> None:
        self.context.chunk_result = chunk_result
        visible_result = chunk_result
        if not include_chunks:
            visible_result = chunk_result.model_copy(update={"chunks": []})
        self.context.response.chunk_result = visible_result

    def set_persistence(self, persistence: PersistenceResult) -> None:
        self.context.persistence = persistence
        self.context.response.persistence = persistence

    def success(self, stage: PipelineStageName, message: str) -> None:
        self._append_stage(stage, "success", message)

    def record(
        self,
        stage: PipelineStageName,
        status: PipelineStatus,
        message: str,
    ) -> None:
        self._append_stage(stage, status, message)

    def failed(
        self,
        stage: PipelineStageName,
        message: str,
        *,
        stop: bool = False,
    ) -> None:
        self._append_stage(stage, "failed", message)
        if stop:
            self.context.stop()

    def skipped(self, stage: PipelineStageName, message: str) -> None:
        self._append_stage(stage, "skipped", message)

    def record_persistence_stage(self) -> None:
        if self.context.persistence is None:
            raise RuntimeError("流水线结束时缺少落库结果。")

        status: PipelineStatus = (
            "success"
            if self.context.persistence.persisted or not self.context.persist
            else "failed"
        )
        self._append_stage(
            "document_persistence",
            status,
            self.context.persistence.message,
        )

    def parsing_message(self, parsed_text: ParsedTextResult) -> str:
        if not parsed_text.suspected_scanned and parsed_text.parse_method == "direct":
            return "已完成全文组装。"
        if parsed_text.parse_method == "mixed":
            return self.join_messages(parsed_text.notes, "已完成直接解析与 OCR 混合组装。")
        if parsed_text.parse_method == "ocr":
            return self.join_messages(parsed_text.notes, "已完成 OCR 文本组装。")
        return self.join_messages(
            parsed_text.notes,
            "已完成全文组装，但文档仍疑似扫描件。",
        )

    def join_messages(self, messages: list[str], fallback: str) -> str:
        normalized = [message.strip() for message in messages if message.strip()]
        if not normalized:
            return fallback
        return "；".join(normalized)

    def build(self) -> PolicyPipelineResponse:
        return self.context.response

    def _append_stage(
        self,
        stage: PipelineStageName,
        status: PipelineStatus,
        message: str,
    ) -> None:
        self.context.response.stages.append(
            PipelineStageResult(
                stage=stage,
                status=status,
                message=message,
            )
        )
