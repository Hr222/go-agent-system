from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ValidationError

from app.business.agents.tender.application.chunking import TenderChunkPlanner
from app.business.agents.tender.application.prompts import (
    TENDER_MERGE_PROMPT_VERSION,
    build_tender_boundary_verification_request,
    build_tender_chunk_request,
    build_tender_merge_request,
    build_tender_skeleton_request,
)
from app.business.agents.tender.contracts import (
    TenderAnalysis,
    TenderAnalysisBudget,
    TenderBoundaryContextBlock,
    TenderBoundaryVerification,
    TenderChunkAnalysis,
    TenderChunkPlan,
    TenderDocument,
    TenderExtractFormatSectionCommand,
    TenderExtractFormatSectionResult,
    TenderGenerateSkeletonCommand,
    TenderGenerateSkeletonResult,
    TenderVerifyExtractionBoundaryCommand,
    TenderVerifyExtractionBoundaryResult,
)
from app.business.agents.tender.errors import (
    TenderAnalysisError,
    TenderInputError,
    TenderRenderError,
)
from app.business.agents.tender.ports.chunk_port import TenderChunkPlannerPort
from app.business.agents.tender.ports.document_port import TenderDocumentReaderPort
from app.business.agents.tender.ports.llm_port import StructuredLlmPort
from app.business.agents.tender.ports.renderer_port import TenderSkeletonRendererPort
from app.platform.llm.contracts import StructuredLlmRequest, StructuredLlmResult
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError
from app.shared.logging import get_logger

logger = get_logger("app.business.agents.tender.application")


class TenderApplication:
    """编排一次招标文件分析和投标骨架生成。"""

    def __init__(
        self,
        *,
        llm: StructuredLlmPort | None = None,
        reader: TenderDocumentReaderPort,
        renderer: TenderSkeletonRendererPort,
        planner: TenderChunkPlannerPort | None = None,
        boundary_llm: StructuredLlmPort | None = None,
        verify_llm: StructuredLlmPort | None = None,
        chunk_llm: StructuredLlmPort | None = None,
        merge_llm: StructuredLlmPort | None = None,
        budget: TenderAnalysisBudget | None = None,
    ) -> None:
        self.llm = llm or boundary_llm or chunk_llm or merge_llm
        if self.llm is None:
            raise ValueError("Tender Application 至少需要一个结构化 LLM。")
        self.reader = reader
        self.renderer = renderer
        self.planner = planner or TenderChunkPlanner()
        self.boundary_llm = boundary_llm
        self.verify_llm = verify_llm or boundary_llm
        self.chunk_llm = chunk_llm
        self.merge_llm = merge_llm
        self.budget = budget or TenderAnalysisBudget()

    def execute(
        self, command: TenderGenerateSkeletonCommand
    ) -> TenderGenerateSkeletonResult:
        self._validate_command(command)
        document = self.reader.read(file_name=command.file_name, content=command.content)

        if len(document.content) > self.budget.chunk_threshold_bytes:
            plan = self.planner.plan(document=document, budget=self.budget)
            analysis, model, prompt_version = self._execute_chunked(
                document=document,
                plan=plan,
                user_focus=command.user_focus,
            )
        elif self.boundary_llm is not None:
            analysis, model, prompt_version = self._execute_boundary_driven(
                document=document,
                user_focus=command.user_focus,
            )
        else:
            plan = self.planner.plan(document=document, budget=self.budget)
            if self.chunk_llm is None and self.merge_llm is None and len(plan.chunks) == 1:
                analysis, model, prompt_version = self._execute_legacy(document, command)
            else:
                analysis, model, prompt_version = self._execute_chunked(
                    document=document,
                    plan=plan,
                    user_focus=command.user_focus,
                )
        try:
            artifacts = self.renderer.render(document=document, analysis=analysis)
        except TenderRenderError:
            raise
        except Exception as exc:
            raise TenderRenderError("投标骨架文件生成失败。") from exc
        return TenderGenerateSkeletonResult(
            analysis=analysis,
            artifacts=artifacts,
            model=model,
            prompt_version=prompt_version,
        )

    def extract_bid_format_section(
        self, command: TenderExtractFormatSectionCommand
    ) -> TenderExtractFormatSectionResult:
        """Copy a confirmed source range without asking the model to decide."""

        self._validate_source_command(command.file_name, command.content)
        document = self.reader.read(file_name=command.file_name, content=command.content)
        start_position, end_position = self._boundary_positions(
            document,
            start_block_id=command.start_block_id,
            end_block_id=command.end_block_id,
        )
        selected_blocks = document.blocks[start_position : end_position + 1]
        output_name = command.output_name or f"{_source_stem(document.file_name)}_bid_format"
        try:
            artifact = self.renderer.extract_range(
                document=document,
                start_block_id=command.start_block_id,
                end_block_id=command.end_block_id,
                output_name=output_name,
            )
        except TenderRenderError:
            raise
        except Exception as exc:
            raise TenderRenderError("Bid format section extraction failed.") from exc
        return TenderExtractFormatSectionResult(
            artifact=artifact,
            start_block_id=command.start_block_id,
            end_block_id=command.end_block_id,
            block_count=len(selected_blocks),
            table_count=sum(block.kind == "table" for block in selected_blocks),
        )

    def verify_extraction_boundary(
        self, command: TenderVerifyExtractionBoundaryCommand
    ) -> TenderVerifyExtractionBoundaryResult:
        """Return source context; boundary decisions remain with the Agent."""

        self._validate_source_command(command.file_name, command.content)
        if not isinstance(command.context_radius, int) or isinstance(
            command.context_radius, bool
        ) or not 0 <= command.context_radius <= 20:
            raise TenderInputError("context_radius must be an integer between 0 and 20.")
        document = self.reader.read(file_name=command.file_name, content=command.content)
        start_position, end_position = self._boundary_positions(
            document,
            start_block_id=command.start_block_id,
            end_block_id=command.end_block_id,
        )
        selected_positions: set[int] = set()
        for center in (start_position, end_position):
            selected_positions.update(
                range(
                    max(0, center - command.context_radius),
                    min(len(document.blocks), center + command.context_radius + 1),
                )
            )
        context = tuple(
            TenderBoundaryContextBlock(
                block_id=block.block_id,
                kind=block.kind,
                text=block.text,
                order=block.order,
                position=position,
                heading_path=block.heading_path,
            )
            for position, block in enumerate(document.blocks)
            if position in selected_positions
        )
        return TenderVerifyExtractionBoundaryResult(
            start_block_id=command.start_block_id,
            end_block_id=command.end_block_id,
            start_position=start_position,
            end_position=end_position,
            context=context,
        )

    def _execute_boundary_driven(
        self,
        *,
        document: TenderDocument,
        user_focus: str | None,
    ) -> tuple[TenderAnalysis, str, str]:
        """Run the proven boundary-first V1 flow through Structured JSON.

        The external protocol remains MCP/HTTP. Internally the model returns the
        same decisions the reference extractor made: one format region and exact
        per-volume source ranges. File copying stays deterministic.
        """

        request = build_tender_skeleton_request(
            source_text=document.source_text,
            user_focus=user_focus,
        )
        try:
            raw_result = self.boundary_llm.invoke(request, TenderAnalysis)
        except (ServiceNotConfiguredError, UpstreamServiceError):
            raise
        except Exception as exc:
            raise TenderAnalysisError("招标文件结构化分析失败。") from exc

        analysis = self._validated_analysis(
            raw_result,
            document_block_ids=set(document.block_map()),
            document=document,
            require_explicit_boundaries=True,
            require_complete_single_range=False,
        )

        if analysis.package_type == "single_volume":
            analysis = self._verify_single_volume_boundary(
                document=document,
                analysis=analysis,
            )

        return analysis, raw_result.model, raw_result.prompt_version

    def _verify_single_volume_boundary(
        self,
        *,
        document: TenderDocument,
        analysis: TenderAnalysis,
    ) -> TenderAnalysis:
        if self.verify_llm is None:
            raise TenderAnalysisError("单卷格式边界复核器未配置。")
        start_id = analysis.format_start_block_id
        end_id = analysis.format_end_block_id
        if start_id is None or end_id is None:
            raise TenderAnalysisError("单卷格式区域缺少边界。")

        request = build_tender_boundary_verification_request(
            boundary_context=self._boundary_context(
                document=document,
                start_block_id=start_id,
                end_block_id=end_id,
            ),
            proposed_start_block_id=start_id,
            proposed_end_block_id=end_id,
        )
        try:
            result = self.verify_llm.invoke(request, TenderBoundaryVerification)
        except (ServiceNotConfiguredError, UpstreamServiceError):
            raise
        except Exception as exc:
            raise TenderAnalysisError("单卷格式边界复核失败。") from exc

        verification = result.value
        if not isinstance(verification, TenderBoundaryVerification):
            try:
                verification = TenderBoundaryVerification.model_validate(verification)
            except Exception as exc:
                raise TenderAnalysisError("单卷格式边界复核结果无效。") from exc

        if not verification.should_adjust:
            return analysis
        if (
            verification.new_start_block_id is None
            or verification.new_end_block_id is None
        ):
            raise TenderAnalysisError("单卷格式边界复核要求调整但未返回新边界。")

        output = analysis.outputs[0]
        adjusted = analysis.model_copy(
            update={
                "format_start_block_id": verification.new_start_block_id,
                "format_end_block_id": verification.new_end_block_id,
                "outputs": [
                    output.model_copy(
                        update={
                            "source_start_block_id": verification.new_start_block_id,
                            "source_end_block_id": verification.new_end_block_id,
                        }
                    )
                ],
            }
        )
        return self._validated_analysis(
            StructuredLlmResult(
                value=adjusted,
                model=result.model,
                prompt_version=result.prompt_version,
            ),
            document_block_ids=set(document.block_map()),
            document=document,
            require_explicit_boundaries=True,
        )

    @staticmethod
    def _boundary_context(
        *,
        document: TenderDocument,
        start_block_id: str,
        end_block_id: str,
        radius: int = 3,
    ) -> str:
        blocks = list(document.blocks)
        positions = {block.block_id: index for index, block in enumerate(blocks)}
        if start_block_id not in positions or end_block_id not in positions:
            raise TenderAnalysisError("边界复核引用了不存在的源文档块。")
        selected_positions = set()
        for boundary_id in (start_block_id, end_block_id):
            center = positions[boundary_id]
            selected_positions.update(
                range(max(0, center - radius), min(len(blocks), center + radius + 1))
            )
        return "\n".join(
            f"[evidence_id={block.block_id}] [body_order={block.order}] "
            f"[block_kind={block.kind}] {block.text}"
            for index, block in enumerate(blocks)
            if index in selected_positions
        )

    def _execute_legacy(
        self, document: TenderDocument, command: TenderGenerateSkeletonCommand
    ) -> tuple[TenderAnalysis, str, str]:
        request = build_tender_skeleton_request(
            source_text=document.source_text,
            user_focus=command.user_focus,
        )
        try:
            raw_result = self.llm.invoke(request, TenderAnalysis)
        except (ServiceNotConfiguredError, UpstreamServiceError):
            raise
        except Exception as exc:
            raise TenderAnalysisError("招标文件结构化分析失败。") from exc
        analysis = self._validated_analysis(
            raw_result,
            document_block_ids=set(document.block_map()),
        )
        return analysis, raw_result.model, raw_result.prompt_version

    def _execute_chunked(
        self,
        *,
        document: TenderDocument,
        plan: TenderChunkPlan,
        user_focus: str | None,
    ) -> tuple[TenderAnalysis, str, str]:
        call_count = 0
        started = perf_counter()
        chunk_llm = self.chunk_llm or self.llm
        merge_llm = self.merge_llm or self.llm
        local_results: list[TenderChunkAnalysis] = []
        model = "unknown"
        prompt_version = TENDER_MERGE_PROMPT_VERSION

        for chunk in plan.chunks:
            request = build_tender_chunk_request(chunk=chunk, user_focus=user_focus)
            raw_result, call_count = self._invoke_bounded(
                llm=chunk_llm,
                request=request,
                schema=TenderChunkAnalysis,
                stage="chunk",
                target_id=chunk.chunk_id,
                call_count=call_count,
                started=started,
                validator=lambda result: self._validate_chunk_result(
                    _as_chunk_analysis(result.value),
                    chunk_id=chunk.chunk_id,
                    chunk_evidence_ids=set(chunk.evidence_ids),
                ),
            )
            model = raw_result.model
            local = _as_chunk_analysis(raw_result.value)
            local_results.append(local)

        current: list[TenderChunkAnalysis | TenderAnalysis] = list(local_results)
        level = 0
        while True:
            level += 1
            batches = _merge_batches(
                current,
                max_items=self.budget.max_merge_items,
                max_chars=self.budget.merge_input_chars,
            )
            merged: list[TenderAnalysis] = []
            for batch_index, items in enumerate(batches, start=1):
                batch_id = f"merge-{level:02d}-{batch_index:03d}"
                request = build_tender_merge_request(items=items, batch_id=batch_id)
                raw_result, call_count = self._invoke_bounded(
                    llm=merge_llm,
                    request=request,
                    schema=TenderAnalysis,
                    stage="merge",
                    target_id=batch_id,
                    call_count=call_count,
                    started=started,
                )
                model = raw_result.model
                prompt_version = raw_result.prompt_version
                merged.append(_as_tender_analysis(raw_result.value))
            if len(merged) == 1:
                final_analysis = merged[0]
                break
            current = merged

        if any(not item.coverage_complete for item in local_results):
            final_analysis = _mark_needs_review(
                final_analysis,
                "部分分块无法完整覆盖，最终分线需要人工确认。",
            )
        final_result = self._validated_analysis(
            StructuredLlmResult(
                value=final_analysis,
                model=model,
                prompt_version=prompt_version,
            ),
            document_block_ids=set(document.block_map()),
        )
        return final_result, model, prompt_version

    def _invoke_bounded(
        self,
        *,
        llm: StructuredLlmPort,
        request: StructuredLlmRequest,
        schema: type[BaseModel],
        stage: str,
        target_id: str,
        call_count: int,
        started: float,
        validator: Callable[[StructuredLlmResult[object]], None] | None = None,
    ) -> tuple[StructuredLlmResult[object], int]:
        last_error: Exception | None = None
        for _attempt in range(self.budget.max_retries + 1):
            if perf_counter() - started > self.budget.max_total_seconds:
                raise TenderAnalysisError("招标分析总耗时超过请求预算。")
            call_count += 1
            if call_count > self.budget.max_llm_calls:
                raise TenderAnalysisError("招标分析调用次数超过请求预算。")
            call_started = perf_counter()
            logger.info(
                "tender llm call start stage=%s target_id=%s prompt_version=%s input_chars=%s",
                stage,
                target_id,
                request.prompt_version,
                len(request.user_prompt),
            )
            try:
                result = llm.invoke(request, schema)
                output_chars = len(
                    json.dumps(result.value.model_dump(mode="json"), ensure_ascii=False)
                )
                if output_chars > self.budget.max_output_chars:
                    raise TenderAnalysisError("招标分析输出超过请求预算。")
                if validator is not None:
                    validator(result)
                logger.info(
                    "tender llm call success stage=%s target_id=%s duration_ms=%.2f "
                    "output_chars=%s",
                    stage,
                    target_id,
                    (perf_counter() - call_started) * 1000,
                    output_chars,
                )
                return result, call_count
            except ServiceNotConfiguredError:
                raise
            except UpstreamServiceError as exc:
                last_error = exc
            except Exception as exc:  # noqa: BLE001 - Port 边界统一转换
                last_error = exc
            logger.warning(
                "tender llm call failed stage=%s target_id=%s duration_ms=%.2f error_type=%s",
                stage,
                target_id,
                (perf_counter() - call_started) * 1000,
                type(last_error).__name__,
            )
        diagnostic_id = f"{stage}-{target_id}"
        failure_code = _failure_code(last_error)
        if isinstance(last_error, UpstreamServiceError):
            raise UpstreamServiceError(
                f"Tender {stage} 调用失败，诊断标识：{diagnostic_id}，失败分类：{failure_code}。"
            ) from last_error
        raise TenderAnalysisError(
            f"Tender {stage} 结果无效，诊断标识：{diagnostic_id}，失败分类：{failure_code}。"
        ) from last_error

    @staticmethod
    def _validate_command(command: TenderGenerateSkeletonCommand) -> None:
        TenderApplication._validate_source_command(command.file_name, command.content)

    @staticmethod
    def _validate_source_command(file_name: str, content: bytes) -> None:
        if not file_name.strip():
            raise TenderInputError("招标文件名称不能为空。")
        if not file_name.lower().endswith(".docx"):
            raise TenderInputError("Tender 只接受 DOCX 招标文件。")
        if not content:
            raise TenderInputError("招标文件不能为空。")

    @staticmethod
    def _boundary_positions(
        document: TenderDocument,
        *,
        start_block_id: str,
        end_block_id: str,
    ) -> tuple[int, int]:
        if not start_block_id.strip() or not end_block_id.strip():
            raise TenderInputError("Extraction boundaries cannot be empty.")
        positions = {block.block_id: position for position, block in enumerate(document.blocks)}
        if start_block_id not in positions or end_block_id not in positions:
            raise TenderInputError("Extraction boundaries must reference source evidence blocks.")
        start_position = positions[start_block_id]
        end_position = positions[end_block_id]
        if start_position > end_position:
            raise TenderInputError("Extraction start boundary must not follow the end boundary.")
        return start_position, end_position

    @staticmethod
    def _validated_analysis(
        raw_result: StructuredLlmResult[object],
        *,
        document_block_ids: set[str],
        document: TenderDocument | None = None,
        require_explicit_boundaries: bool = False,
        require_complete_single_range: bool = True,
    ) -> TenderAnalysis:
        try:
            analysis = (
                raw_result.value
                if isinstance(raw_result.value, TenderAnalysis)
                else TenderAnalysis.model_validate(raw_result.value)
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise TenderAnalysisError("招标分析结果不符合契约。") from exc

        if analysis.package_type == "single_volume" and len(analysis.outputs) != 1:
            raise TenderAnalysisError("单卷分析必须且只能包含一个输出文件。")
        if analysis.package_type == "multi_volume" and len(analysis.outputs) < 2:
            raise TenderAnalysisError("多卷分析至少需要包含两个输出文件。")
        if analysis.package_type == "uncertain" and analysis.status != "needs_review":
            raise TenderAnalysisError("无法确定分线时必须标记为待确认。")
        if analysis.status == "completed" and not analysis.outputs:
            raise TenderAnalysisError("已完成的招标分析必须包含输出文件。")
        evidence_ids = {item.evidence_id for item in analysis.evidence}
        referenced_ids = set(evidence_ids)
        referenced_ids.update(
            filter(None, (analysis.format_start_block_id, analysis.format_end_block_id))
        )
        referenced_ids.update(
            evidence_ref
            for output in analysis.outputs
            for evidence_ref in (
                *output.evidence_refs,
                *filter(
                    None,
                    (output.source_start_block_id, output.source_end_block_id),
                ),
            )
        )
        referenced_ids.update(
            evidence_ref
            for requirement in analysis.key_requirements
            for evidence_ref in requirement.evidence_refs
        )
        missing_ids = sorted(referenced_ids - document_block_ids)
        if missing_ids:
            raise TenderAnalysisError(
                "招标分析引用了源文件中不存在的证据：" + ", ".join(missing_ids)
            )
        if not evidence_ids:
            raise TenderAnalysisError("招标分析必须包含至少一条源文档证据。")
        if require_explicit_boundaries:
            if document is None:
                raise TenderAnalysisError("边界校验缺少源文档。")
            TenderApplication._validate_explicit_boundaries(
                analysis=analysis,
                document=document,
                require_complete_single_range=require_complete_single_range,
            )
        return analysis

    @staticmethod
    def _validate_explicit_boundaries(
        *,
        analysis: TenderAnalysis,
        document: TenderDocument,
        max_gap_blocks: int = 3,
        require_complete_single_range: bool = True,
    ) -> None:
        """Reject ambiguous ranges before the renderer can copy the wrong body."""

        # DOCX body order includes empty XML children omitted by the reader.
        # Use the extracted block sequence when measuring uncovered content.
        position_by_id = {
            block.block_id: position for position, block in enumerate(document.blocks)
        }
        format_start = analysis.format_start_block_id
        format_end = analysis.format_end_block_id
        if format_start is None or format_end is None:
            raise TenderAnalysisError("招标格式区域必须包含起止边界。")
        if format_start not in position_by_id or format_end not in position_by_id:
            raise TenderAnalysisError("招标格式区域引用了不存在的边界。")
        format_start_position = position_by_id[format_start]
        format_end_position = position_by_id[format_end]
        if format_start_position > format_end_position:
            raise TenderAnalysisError("招标格式区域边界顺序错误。")

        ranges: list[tuple[int, int, str]] = []
        names: set[str] = set()
        slugs: set[str] = set()
        for output in analysis.outputs:
            start_id = output.source_start_block_id
            end_id = output.source_end_block_id
            if start_id is None or end_id is None:
                raise TenderAnalysisError(f"输出 {output.name} 缺少精确分册边界。")
            if start_id not in position_by_id or end_id not in position_by_id:
                raise TenderAnalysisError(f"输出 {output.name} 引用了不存在的分册边界。")
            start_position = position_by_id[start_id]
            end_position = position_by_id[end_id]
            if start_position > end_position:
                raise TenderAnalysisError(f"输出 {output.name} 的分册边界顺序错误。")
            if (
                start_position < format_start_position
                or end_position > format_end_position
            ):
                raise TenderAnalysisError(f"输出 {output.name} 超出格式区域边界。")
            if output.name in names or output.slug in slugs:
                raise TenderAnalysisError("招标分析包含重复的分册输出。")
            names.add(output.name)
            slugs.add(output.slug)
            for evidence_ref in output.evidence_refs:
                if evidence_ref not in position_by_id:
                    continue
                evidence_position = position_by_id[evidence_ref]
                if not start_position <= evidence_position <= end_position:
                    raise TenderAnalysisError(
                        f"输出 {output.name} 的证据超出自身分册边界。"
                    )
            ranges.append((start_position, end_position, output.name))

        ranges.sort()
        if analysis.package_type == "single_volume":
            if len(ranges) != 1:
                raise TenderAnalysisError("单卷分析必须且只能包含一个精确范围。")
            start_position, end_position, name = ranges[0]
            if (
                require_complete_single_range
                and (
                    start_position != format_start_position
                    or end_position != format_end_position
                )
            ):
                raise TenderAnalysisError(f"单卷输出 {name} 未覆盖完整格式区域。")
            return

        for previous, current in zip(ranges, ranges[1:]):
            previous_start, previous_end, previous_name = previous
            current_start, _, current_name = current
            if current_start <= previous_end:
                raise TenderAnalysisError(
                    f"分册范围重叠：{previous_name} 与 {current_name}。"
                )
            if current_start - previous_end - 1 > max_gap_blocks:
                raise TenderAnalysisError(
                    f"分册范围存在未覆盖内容：{previous_name} 与 {current_name}。"
                )
        if ranges and format_end_position - ranges[-1][1] > max_gap_blocks:
            raise TenderAnalysisError("最后一个分册没有覆盖到格式区域末尾。")

    @staticmethod
    def _validate_chunk_result(
        result: TenderChunkAnalysis, *, chunk_id: str, chunk_evidence_ids: set[str]
    ) -> None:
        if result.chunk_id != chunk_id:
            raise TenderAnalysisError(
                f"分块结果 ID 不匹配：期望 {chunk_id}，实际 {result.chunk_id}。"
            )
        refs = {item.evidence_id for item in result.evidence}
        refs.update(ref for item in result.requirements for ref in item.evidence_refs)
        refs.update(ref for item in result.output_candidates for ref in item.evidence_refs)
        missing = sorted(refs - chunk_evidence_ids)
        if missing:
            raise TenderAnalysisError(
                f"分块 {result.chunk_id} 引用了不属于当前分块的证据：{', '.join(missing)}"
            )


def _as_chunk_analysis(value: object) -> TenderChunkAnalysis:
    try:
        return (
            value
            if isinstance(value, TenderChunkAnalysis)
            else TenderChunkAnalysis.model_validate(value)
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise TenderAnalysisError("分块结果不符合局部提取契约。") from exc


def _as_tender_analysis(value: object) -> TenderAnalysis:
    try:
        return value if isinstance(value, TenderAnalysis) else TenderAnalysis.model_validate(value)
    except (ValidationError, TypeError, ValueError) as exc:
        raise TenderAnalysisError("归并结果不符合 TenderAnalysis 契约。") from exc


def _merge_batches(
    items: list[TenderChunkAnalysis | TenderAnalysis], *, max_items: int, max_chars: int
) -> list[tuple[TenderChunkAnalysis | TenderAnalysis, ...]]:
    batches: list[tuple[TenderChunkAnalysis | TenderAnalysis, ...]] = []
    current: list[TenderChunkAnalysis | TenderAnalysis] = []
    current_chars = 0
    for item in items:
        item_chars = len(json.dumps(item.model_dump(mode="json"), ensure_ascii=False))
        if item_chars > max_chars:
            raise TenderAnalysisError("归并输入结果超过单次归并预算。")
        if current and (len(current) >= max_items or current_chars + item_chars > max_chars):
            batches.append(tuple(current))
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars
    if current:
        batches.append(tuple(current))
    return batches


def _mark_needs_review(analysis: TenderAnalysis, uncertainty: str) -> TenderAnalysis:
    uncertainties = list(analysis.uncertainties)
    if uncertainty not in uncertainties:
        uncertainties.append(uncertainty)
    return analysis.model_copy(update={"status": "needs_review", "uncertainties": uncertainties})


def _failure_code(error: Exception | None) -> str:
    """将上游错误映射为不含原文的有限诊断分类。"""

    if error is None:
        return "unknown"
    message = str(error).lower()
    if "max_tokens" in message or "截断" in message:
        return "output_truncated"
    if "timeout" in message or "timed out" in message or "超时" in message:
        return "provider_timeout"
    return type(error).__name__


def _source_stem(file_name: str) -> str:
    stem = Path(file_name).stem.strip()
    return stem or "tender"
