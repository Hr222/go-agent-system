from __future__ import annotations

from app.platform.ingestion.contracts import (
    ChunkSplitResult,
    CleanedTextResult,
    ParsedDocumentResult,
    ParsedTextResult,
    PersistenceResult,
    RegisteredFileInfo,
    SectionSplitResult,
)
from app.platform.ingestion.pipeline.context import PipelineContext
from app.platform.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.shared.logging import get_logger

logger = get_logger("app.pipeline.persistence")


class PolicyPersistenceService:
    def __init__(self, write_capability: KnowledgeBaseWriteCapability) -> None:
        self.write_capability = write_capability

    def persist(self, context: PipelineContext) -> PersistenceResult:
        policy_name = context.policy_name_guess
        if not policy_name:
            raise RuntimeError("落库前缺少制度名称。")

        version_label = context.derived_version_label
        if not version_label:
            raise RuntimeError("落库前缺少版本标签。")

        registered_file = self._require_registered_file(context.registered_file)
        parsed_document = self._require_parsed_document(context.parsed_document)
        parsed_text = self._require_parsed_text(context.parsed_text)
        cleaned_text = self._require_cleaned_text(context.cleaned_text)
        section_result = self._require_section_result(context.section_result)
        chunk_result = self._require_chunk_result(context.chunk_result)
        logger.info(
            "开始写入知识库记录 source_path=%s policy_name=%s "
            "version_label=%s sections=%s chunks=%s",
            context.request.source_path,
            policy_name,
            version_label,
            len(section_result.sections),
            len(chunk_result.chunks),
        )

        persisted = self.write_capability.write(
            policy_name=policy_name,
            policy_category=context.request.policy_category,
            responsible_department=context.request.responsible_department,
            target_document_id=context.request.target_document_id,
            registered_file=registered_file,
            version_label=version_label,
            parse_method=parsed_text.parse_method,
            parser_status=parsed_text.parser_status,
            is_scanned=parsed_text.suspected_scanned,
            raw_text=parsed_text.raw_text,
            cleaned_text=cleaned_text,
            blocks=parsed_document.blocks,
            sections=section_result.sections,
            chunks=chunk_result.chunks,
        )
        logger.info(
            "知识库记录写入完成 source_path=%s document_id=%s "
            "version_id=%s version_seq=%s sections=%s chunks=%s",
            context.request.source_path,
            persisted.document_id,
            persisted.version_id,
            persisted.version_seq,
            persisted.section_count,
            persisted.chunk_count,
        )
        return PersistenceResult(
            persisted=True,
            document_id=persisted.document_id,
            version_id=persisted.version_id,
            version_seq=persisted.version_seq,
            version_label=persisted.version_label,
            section_count=persisted.section_count,
            chunk_count=persisted.chunk_count,
            message="已完成制度文档、版本、章节、切块和向量入库。",
        )

    def _require_registered_file(
        self,
        registered_file: RegisteredFileInfo | None,
    ) -> RegisteredFileInfo:
        if registered_file is None:
            raise RuntimeError("落库前缺少文件登记结果。")
        return registered_file

    def _require_parsed_document(
        self,
        parsed_document: ParsedDocumentResult | None,
    ) -> ParsedDocumentResult:
        if parsed_document is None:
            raise RuntimeError("落库前缺少结构化文档解析结果。")
        return parsed_document

    def _require_parsed_text(self, parsed_text: ParsedTextResult | None) -> ParsedTextResult:
        if parsed_text is None:
            raise RuntimeError("落库前缺少文本解析结果。")
        return parsed_text

    def _require_cleaned_text(
        self,
        cleaned_text: CleanedTextResult | None,
    ) -> CleanedTextResult:
        if cleaned_text is None:
            raise RuntimeError("落库前缺少文本清洗结果。")
        return cleaned_text

    def _require_section_result(
        self,
        section_result: SectionSplitResult | None,
    ) -> SectionSplitResult:
        if section_result is None:
            raise RuntimeError("落库前缺少章节拆分结果。")
        return section_result

    def _require_chunk_result(self, chunk_result: ChunkSplitResult | None) -> ChunkSplitResult:
        if chunk_result is None:
            raise RuntimeError("落库前缺少切块结果。")
        return chunk_result
