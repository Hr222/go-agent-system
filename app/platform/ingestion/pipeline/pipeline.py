from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.platform.ingestion.contracts import (
    ParsedDocumentResult,
    PersistenceResult,
    PolicyPipelineRequest,
    PolicyPipelineResponse,
)
from app.platform.ingestion.domain import PolicyIdentityPolicy
from app.platform.ingestion.pipeline.context import PipelineContext, PipelineMode
from app.platform.ingestion.pipeline.persistence import PolicyPersistenceService
from app.platform.ingestion.pipeline.response_builder import PipelineResponseBuilder
from app.platform.ingestion.pipeline.steps.policy_chunking import PolicyChunkingService
from app.platform.ingestion.pipeline.steps.policy_normalizer import PolicyFormatNormalizer
from app.platform.ingestion.pipeline.steps.policy_parser import PolicyParserService
from app.platform.ingestion.pipeline.steps.policy_section_splitter import PolicySectionSplitter
from app.platform.ingestion.pipeline.steps.policy_text_assembler import PolicyTextAssemblerService
from app.platform.ingestion.pipeline.steps.policy_text_cleaner import PolicyTextCleaner
from app.platform.ingestion.ports import FileRegistrationPort, OcrPort
from app.platform.knowledge.application.write_capability import KnowledgeBaseWriteCapability
from app.platform.llm.ports import TextEmbeddingPort
from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger("app.pipeline.policy")


class PolicyPipelineService:
    """编排制度文档处理流水线。"""

    def __init__(
        self,
        write_capability: KnowledgeBaseWriteCapability | None = None,
        *,
        embedding_service: TextEmbeddingPort | None = None,
        file_service: FileRegistrationPort,
        ocr_service: OcrPort,
    ) -> None:
        workspace_root = Path(settings.policy_pipeline_workspace)
        self.write_capability = write_capability
        self.embedding_service = embedding_service
        self.persistence_service = (
            PolicyPersistenceService(write_capability)
            if write_capability is not None
            else None
        )
        self.file_service = file_service
        self.normalizer = PolicyFormatNormalizer(workspace_root=workspace_root)
        self.parser = PolicyParserService()
        self.ocr_service = ocr_service
        self.text_assembler = PolicyTextAssemblerService()
        self.cleaner = PolicyTextCleaner()
        self.section_splitter = PolicySectionSplitter()
        self.chunking_service = PolicyChunkingService()
        self.identity_policy = PolicyIdentityPolicy()

    def preview(self, request: PolicyPipelineRequest) -> PolicyPipelineResponse:
        return self._run(request=request, mode="preview", persist=False)

    def ingest(self, request: PolicyPipelineRequest) -> PolicyPipelineResponse:
        if self.write_capability is None:
            raise RuntimeError("入库模式必须提供知识库写入能力。")
        return self._run(request=request, mode="ingest", persist=True)

    def _run(
        self,
        *,
        request: PolicyPipelineRequest,
        mode: PipelineMode,
        persist: bool,
    ) -> PolicyPipelineResponse:
        context = PipelineContext(request=request, mode=mode, persist=persist)
        builder = PipelineResponseBuilder(context)
        logger.info(
            "流水线开始 mode=%s persist=%s source_path=%s category=%s",
            mode,
            persist,
            request.source_path,
            request.policy_category,
        )

        # 阶段顺序是入库链路的核心约束：后续阶段只能消费前一阶段的结果，
        # 预览或准入失败时通过 stop_requested 提前结束，不进入持久化。
        stages = (
            self._register_file,
            self._validate_intake,
            self._normalize,
            self._route_parser,
            self._parse_document,
            self._run_ocr,
            self._assemble_text,
            self._guard_ingest_eligibility,
            self._clean_text,
            self._split_sections,
            self._split_chunks,
            self._embed_if_needed,
            self._persist_if_needed,
        )
        for stage in stages:
            stage_name = stage.__name__.removeprefix("_")
            started = perf_counter()
            logger.info("阶段开始 mode=%s stage=%s", mode, stage_name)
            try:
                stage(context, builder)
            except Exception:
                duration_ms = (perf_counter() - started) * 1000
                logger.exception(
                    "阶段失败 mode=%s stage=%s duration_ms=%.2f",
                    mode,
                    stage_name,
                    duration_ms,
                )
                raise

            duration_ms = (perf_counter() - started) * 1000
            logger.info(
                "阶段完成 mode=%s stage=%s stop_requested=%s duration_ms=%.2f",
                mode,
                stage_name,
                context.stop_requested,
                duration_ms,
            )
            if context.stop_requested:
                logger.warning("流水线提前结束 mode=%s stage=%s", mode, stage_name)
                break

        response = builder.build()
        logger.info(
            "流水线结束 mode=%s stage_count=%s persisted=%s source_path=%s",
            mode,
            len(response.stages),
            response.persistence.persisted if response.persistence is not None else False,
            request.source_path,
        )
        return response

    def _register_file(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        registered_file = self.file_service.register_file(context.request.source_path)
        builder.set_registered_file(registered_file)
        builder.set_policy_identity(
            policy_name_guess=self.identity_policy.guess_policy_name(
                file_name=registered_file.file_name,
            ),
            derived_version_label=self.identity_policy.build_version_label(
                explicit_label=context.request.version_label,
                modified_at_text=registered_file.source_modified_at.strftime("%Y%m%d"),
            ),
        )
        builder.success("file_registration", "已完成源文件登记。")

    def _validate_intake(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.registered_file is None:
            raise RuntimeError("执行准入校验前缺少文件登记结果。")

        validation = self.file_service.validate_intake(context.registered_file)
        builder.set_validation(validation)
        if not validation.is_allowed:
            builder.failed(
                "intake_validation",
                builder.join_messages(validation.warnings, "文件未通过准入校验。"),
                stop=True,
            )
            return
        builder.success("intake_validation", "文件通过准入校验。")

    def _normalize(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.registered_file is None:
            raise RuntimeError("执行格式归一化前缺少文件登记结果。")

        normalization = self.normalizer.normalize(context.registered_file)
        builder.set_normalization(normalization)
        if normalization.status == "failed":
            builder.failed("format_normalization", normalization.message, stop=True)
            return
        if normalization.status == "skipped":
            builder.skipped("format_normalization", normalization.message)
            return
        builder.success("format_normalization", normalization.message)

    def _route_parser(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.normalization is None:
            raise RuntimeError("执行解析器选择前缺少格式归一化结果。")

        parse_routing = self.parser.route_parser(context.normalization.normalized_path)
        builder.set_parse_routing(parse_routing)
        builder.success("parse_routing", f"已选择解析器：{parse_routing.parser_name}。")

    def _parse_document(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.normalization is None:
            raise RuntimeError("执行文本解析前缺少格式归一化结果。")
        if context.parse_routing is None:
            raise RuntimeError("执行文本解析前缺少解析器选择结果。")

        parsed_document = self.parser.parse_document(
            source_path=context.normalization.normalized_path,
            parse_method=context.parse_routing.parse_method,
        )
        builder.set_parsed_document(parsed_document)
        if parsed_document.parser_status == "failed":
            builder.failed(
                "document_parsing",
                builder.join_messages(parsed_document.notes, "结构化文档解析失败。"),
                stop=True,
            )
            return
        builder.success("document_parsing", "已完成有序 block 解析。")

    def _run_ocr(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.parsed_document is None:
            raise RuntimeError("执行 OCR 前缺少结构化文档解析结果。")

        original_document = context.parsed_document
        ocr_result = self.ocr_service.process(original_document, persist=context.persist)
        builder.set_ocr_result(ocr_result)

        updated_document = original_document.model_copy(
            update={
                "blocks": ocr_result.blocks,
                "notes": [*original_document.notes, *ocr_result.notes],
            }
        )
        builder.set_parsed_document(updated_document)

        builder.record(
            "ocr_processing",
            self._resolve_ocr_stage_status(
                document=original_document,
                ocr_applied=ocr_result.applied,
                failed_blocks=ocr_result.failed_blocks,
            ),
            builder.join_messages(ocr_result.notes, "当前无需执行 OCR。"),
        )

    def _assemble_text(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.parsed_document is None:
            raise RuntimeError("执行全文组装前缺少结构化文档解析结果。")

        parse_method = (
            context.ocr_result.parse_method if context.ocr_result is not None else "direct"
        )
        parsed_text = self.text_assembler.assemble(
            context.parsed_document,
            parse_method=parse_method,
        )
        builder.set_parsed_text(parsed_text)
        if parsed_text.parser_status == "failed":
            builder.failed(
                "text_assembly",
                builder.join_messages(parsed_text.notes, "全文组装失败。"),
                stop=True,
            )
            return
        builder.success("text_assembly", builder.parsing_message(parsed_text))

    def _guard_ingest_eligibility(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if not context.persist:
            builder.skipped("ingest_guard", "预览模式不执行入库拦截判断。")
            return
        if context.parsed_text is None:
            return

        effective_text = context.parsed_text.raw_text.strip()
        if effective_text:
            builder.success("ingest_guard", "文本满足入库条件。")
            return

        message = "文档在直接解析和 OCR 后仍未形成有效正文，入库前终止。"
        builder.set_persistence(
            PersistenceResult(
                persisted=False,
                message=message,
            )
        )
        builder.failed("ingest_guard", message, stop=True)

    def _clean_text(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.parsed_text is None:
            raise RuntimeError("执行文本清洗前缺少文本解析结果。")

        cleaned_text = self.cleaner.clean(context.parsed_text)
        builder.set_cleaned_text(cleaned_text)
        builder.success("text_cleaning", "已完成文本清洗。")

    def _split_sections(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.cleaned_text is None:
            raise RuntimeError("执行章节拆分前缺少文本清洗结果。")

        section_result = self.section_splitter.split(context.cleaned_text)
        builder.set_section_result(section_result)
        builder.success(
            "section_splitting",
            f"已拆分出 {section_result.total_sections} 个章节。",
        )

    def _split_chunks(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.section_result is None:
            raise RuntimeError("执行切块前缺少章节拆分结果。")

        chunk_result = self.chunking_service.split(context.section_result)
        logger.info(
            "切块完成 source_path=%s total_sections=%s total_chunks=%s sample_chunks=%s",
            context.request.source_path,
            context.section_result.total_sections,
            chunk_result.total_chunks,
            len(chunk_result.sample_chunks),
        )
        builder.set_chunk_result(chunk_result)
        builder.success("chunk_splitting", f"已生成 {chunk_result.total_chunks} 个切块。")

    def _embed_if_needed(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.chunk_result is None:
            raise RuntimeError("执行向量生成前缺少切块结果。")

        if not context.persist:
            builder.skipped("embedding_generation", "预览模式不生成向量。")
            return

        if self.embedding_service is None:
            raise RuntimeError("入库模式缺少向量生成适配器。")
        logger.info(
            "请求生成向量 source_path=%s total_chunks=%s",
            context.request.source_path,
            context.chunk_result.total_chunks,
        )
        chunks = context.chunk_result.chunks
        vectors = self.embedding_service.embed_texts([chunk.chunk_text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise RuntimeError("向量返回数量与切块数量不一致。")
        embedded_chunks = [
            chunk.model_copy(update={"embedding": vector})
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        embedded_chunk_result = context.chunk_result.model_copy(update={"chunks": embedded_chunks})
        builder.set_chunk_result(embedded_chunk_result)
        builder.success(
            "embedding_generation",
            f"已为 {len(embedded_chunks)} 个切块生成向量。",
        )

    def _persist_if_needed(
        self,
        context: PipelineContext,
        builder: PipelineResponseBuilder,
    ) -> None:
        if context.chunk_result is None:
            raise RuntimeError("执行落库前缺少切块结果。")

        if not context.persist:
            builder.set_persistence(
                PersistenceResult(
                    persisted=False,
                    chunk_count=context.chunk_result.total_chunks,
                    message="预览模式不写入数据库。",
                )
            )
            builder.skipped("chunk_persistence", "预览模式跳过切块落库。")
            builder.record_persistence_stage()
            return

        if self.persistence_service is None:
            raise RuntimeError("入库模式缺少持久化服务。")

        persistence = self.persistence_service.persist(context)
        logger.info(
            "落库完成 source_path=%s document_id=%s version_id=%s section_count=%s chunk_count=%s",
            context.request.source_path,
            persistence.document_id,
            persistence.version_id,
            persistence.section_count,
            persistence.chunk_count,
        )
        builder.set_persistence(persistence)
        builder.success(
            "chunk_persistence",
            f"已写入 {persistence.chunk_count} 个切块及其向量。",
        )
        builder.record_persistence_stage()

    def _resolve_ocr_stage_status(
        self,
        *,
        document: ParsedDocumentResult,
        ocr_applied: bool,
        failed_blocks: int,
    ) -> str:
        # “没有 OCR 场景”和“OCR 没跑出来结果”需要分开，
        # 否则审核和排障时很难判断是真跳过还是实际失败。
        needs_ocr = any(
            block.block_type == "image"
            and (block.metadata.get("image_bytes") or block.metadata.get("pdf_page_render"))
            for block in document.blocks
        )
        if not needs_ocr:
            return "skipped"
        if ocr_applied:
            return "success"
        if failed_blocks > 0:
            return "failed"
        return "skipped"
