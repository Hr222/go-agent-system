from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.business.agents.tender.application.chunking import TenderChunkPlanner
from app.business.agents.tender.application.service import TenderApplication
from app.business.agents.tender.contracts import (
    TenderAnalysis,
    TenderAnalysisBudget,
    TenderChunkAnalysis,
    TenderChunkOutputCandidate,
    TenderDocument,
    TenderDocumentBlock,
    TenderGenerateSkeletonCommand,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.business.agents.tender.errors import TenderAnalysisError
from app.platform.llm.contracts import StructuredLlmRequest, StructuredLlmResult
from app.shared.exceptions import UpstreamServiceError


def _document() -> TenderDocument:
    blocks = tuple(
        TenderDocumentBlock(
            block_id=f"evidence-{index}",
            kind="paragraph",
            text=text,
            order=index,
            heading_path=("第一章",) if index < 3 else ("第二章",),
        )
        for index, text in enumerate(
            ("招标项目说明 " + "甲" * 90, "投标文件组成 " + "乙" * 90, "提交要求 " + "丙" * 90),
            start=1,
        )
    )
    return TenderDocument(
        file_name="招标文件.docx",
        content=b"source",
        blocks=blocks,
        source_text="\n".join(block.text for block in blocks),
    )


def test_chunk_planner_preserves_order_and_evidence_without_truncation() -> None:
    plan = TenderChunkPlanner().plan(
        document=_document(),
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_chunks=10),
    )

    assert len(plan.chunks) >= 3
    assert [evidence for chunk in plan.chunks for evidence in chunk.evidence_ids] == [
        "evidence-1",
        "evidence-2",
        "evidence-3",
    ]
    assert "丙" * 90 in "\n".join(chunk.text for chunk in plan.chunks)
    assert [chunk.sequence for chunk in plan.chunks] == list(
        range(1, len(plan.chunks) + 1)
    )


def test_chunk_planner_repeats_table_header() -> None:
    document = TenderDocument(
        file_name="招标文件.docx",
        content=b"source",
        source_text="",
        blocks=(
            TenderDocumentBlock(
                block_id="evidence-table",
                kind="table",
                text="",
                table_rows=(
                    ("序号", "要求"),
                    ("1", "甲" * 80),
                    ("2", "乙" * 80),
                ),
                table_header=("序号", "要求"),
            ),
        ),
    )
    chunks = TenderChunkPlanner().plan(
        document=document,
        budget=TenderAnalysisBudget(chunk_input_chars=128),
    ).chunks

    assert len(chunks) == 2
    assert all("序号 | 要求" in chunk.text for chunk in chunks)
    assert all(chunk.evidence_ids == ("evidence-table",) for chunk in chunks)


@dataclass
class FakeReader:
    document: TenderDocument

    def read(self, *, file_name: str, content: bytes) -> TenderDocument:
        return self.document


@dataclass
class FakeRenderer:
    calls: int = 0

    def render(self, *, document: TenderDocument, analysis: TenderAnalysis):
        self.calls += 1
        return ()


class ChunkedFakeLlm:
    def __init__(self, document: TenderDocument) -> None:
        self.document = document
        self.calls: list[tuple[str, type[object]]] = []

    def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
        self.calls.append((request.prompt_version, output_schema))
        if output_schema is TenderChunkAnalysis:
            chunk_id = request.user_prompt.split("分块 ID：", 1)[1].split("\n", 1)[0]
            evidence_id = request.user_prompt.split("[evidence_id=", 1)[1].split("]", 1)[0]
            value = TenderChunkAnalysis(
                chunk_id=chunk_id,
                requirements=[],
                output_candidates=[
                    TenderChunkOutputCandidate(
                        label="投标文件", evidence_refs=[evidence_id]
                    )
                ],
                evidence=[],
            )
            return StructuredLlmResult(
                value=value, model="fake", prompt_version=request.prompt_version
            )
        evidence_id = "evidence-1"
        value = TenderAnalysis(
            status="completed",
            package_type="single_volume",
            summary="已归并",
            outputs=[
                TenderOutputPlan(
                    name="投标文件",
                    slug="bid",
                    document_label="投标文件",
                    evidence_refs=[evidence_id],
                )
            ],
            evidence=[
                TenderSourceEvidence(
                    evidence_id=evidence_id, location="第一章", quote="招标项目说明"
                )
            ],
        )
        return StructuredLlmResult(value=value, model="fake", prompt_version=request.prompt_version)


def test_application_uses_local_extraction_then_bounded_global_merge() -> None:
    document = _document()
    llm = ChunkedFakeLlm(document)
    renderer = FakeRenderer()
    application = TenderApplication(
        llm=llm,
        chunk_llm=llm,
        merge_llm=llm,
        reader=FakeReader(document),
        renderer=renderer,
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_merge_items=2),
    )

    result = application.execute(
        TenderGenerateSkeletonCommand(file_name="招标文件.docx", content=b"source")
    )

    assert [version for version, _ in llm.calls[:3]] == [
        "tender-chunk-v1-compact-format-20260731",
        "tender-chunk-v1-compact-format-20260731",
        "tender-chunk-v1-compact-format-20260731",
    ]
    assert llm.calls[-1][0] == "tender-merge-v1-compact-format-20260731"
    assert result.analysis.package_type == "single_volume"
    assert renderer.calls == 1


def test_application_forces_chunked_analysis_above_threshold() -> None:
    document = _document()
    llm = ChunkedFakeLlm(document)
    application = TenderApplication(
        llm=llm,
        boundary_llm=llm,
        verify_llm=llm,
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(
            chunk_threshold_bytes=1,
            chunk_input_chars=128,
            max_merge_items=2,
        ),
    )

    result = application.execute(
        TenderGenerateSkeletonCommand(file_name="招标文件.docx", content=document.content)
    )

    assert result.analysis.package_type == "single_volume"
    assert llm.calls[0][0] == "tender-chunk-v1-compact-format-20260731"
    assert all(version != "tender-skeleton-v1-boundary-copy-20260804" for version, _ in llm.calls)


def test_application_rejects_chunk_evidence_from_another_chunk() -> None:
    document = _document()

    class InvalidLlm(ChunkedFakeLlm):
        def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
            result = super().invoke(request, output_schema)
            if output_schema is TenderChunkAnalysis:
                result.value.output_candidates[0].evidence_refs = ["missing"]
            return result

    application = TenderApplication(
        llm=InvalidLlm(document),
        chunk_llm=InvalidLlm(document),
        merge_llm=InvalidLlm(document),
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(chunk_input_chars=128),
    )

    with pytest.raises(TenderAnalysisError, match="Tender chunk"):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_application_retries_provider_failure_with_bounded_diagnostic() -> None:
    document = _document()

    class FlakyLlm(ChunkedFakeLlm):
        def __init__(self, document: TenderDocument) -> None:
            super().__init__(document)
            self.failed = False

        def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
            if not self.failed:
                self.failed = True
                raise UpstreamServiceError("provider raw response")
            return super().invoke(request, output_schema)

    llm = FlakyLlm(document)
    application = TenderApplication(
        llm=llm,
        chunk_llm=llm,
        merge_llm=llm,
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_retries=1),
    )

    result = application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))

    assert result.analysis.package_type == "single_volume"
    assert llm.failed is True
    assert len(llm.calls) >= 4


def test_application_classifies_truncated_provider_output_without_raw_content() -> None:
    document = _document()

    class TruncatedLlm(ChunkedFakeLlm):
        def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
            del request, output_schema
            raise UpstreamServiceError("structured output reached max_tokens")

    application = TenderApplication(
        llm=TruncatedLlm(document),
        chunk_llm=TruncatedLlm(document),
        merge_llm=TruncatedLlm(document),
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_retries=0),
    )

    with pytest.raises(UpstreamServiceError, match="output_truncated"):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_application_retries_chunk_evidence_validation_failure() -> None:
    document = _document()

    class FlakyLlm(ChunkedFakeLlm):
        def __init__(self, document: TenderDocument) -> None:
            super().__init__(document)
            self.invalid = True

        def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
            result = super().invoke(request, output_schema)
            if output_schema is TenderChunkAnalysis and self.invalid:
                self.invalid = False
                result.value.output_candidates[0].evidence_refs = ["missing"]
            return result

    llm = FlakyLlm(document)
    application = TenderApplication(
        llm=llm,
        chunk_llm=llm,
        merge_llm=llm,
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_retries=1),
    )

    result = application.execute(
        TenderGenerateSkeletonCommand("鎷涙爣鏂囦欢.docx", b"source")
    )

    assert result.analysis.package_type == "single_volume"
    assert llm.invalid is False


def test_application_rejects_request_when_total_budget_is_exhausted() -> None:
    document = _document()
    llm = ChunkedFakeLlm(document)
    application = TenderApplication(
        llm=llm,
        chunk_llm=llm,
        merge_llm=llm,
        reader=FakeReader(document),
        renderer=FakeRenderer(),
        budget=TenderAnalysisBudget(chunk_input_chars=128, max_total_seconds=0.0),
    )

    with pytest.raises(TenderAnalysisError, match="总耗时"):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))
