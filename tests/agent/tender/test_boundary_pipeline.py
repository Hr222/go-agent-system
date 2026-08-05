from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderBoundaryVerification,
    TenderDocument,
    TenderDocumentBlock,
    TenderGenerateSkeletonCommand,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.modules.agent.tender.errors import TenderAnalysisError
from app.modules.llm.contracts import StructuredLlmRequest, StructuredLlmResult


def _document() -> TenderDocument:
    blocks = tuple(
        TenderDocumentBlock(
            block_id=f"evidence-{index}",
            kind="paragraph",
            text=text,
            order=index,
            heading_path=("投标文件格式",),
        )
        for index, text in enumerate(
            (
                "投标文件格式",
                "编制说明",
                "商务技术文件封面",
                "商务技术响应表",
                "报价文件封面",
                "投标报价表",
            ),
            start=1,
        )
    )
    return TenderDocument(
        file_name="招标文件.docx",
        content=b"docx",
        blocks=blocks,
        source_text="\n".join(block.text for block in blocks),
    )


def _evidence(document: TenderDocument) -> list[TenderSourceEvidence]:
    return [
        TenderSourceEvidence(
            evidence_id=block.block_id,
            location=block.text,
            quote=block.text,
        )
        for block in document.blocks
    ]


def _analysis(
    document: TenderDocument,
    *,
    package_type: str = "multi_volume",
    outputs: list[TenderOutputPlan] | None = None,
) -> TenderAnalysis:
    if outputs is None:
        outputs = [
            TenderOutputPlan(
                name="商务技术文件",
                slug="commercial-technical",
                document_label="商务技术文件",
                evidence_refs=["evidence-3", "evidence-4"],
                source_start_block_id="evidence-3",
                source_end_block_id="evidence-4",
            ),
            TenderOutputPlan(
                name="报价文件",
                slug="pricing",
                document_label="报价文件",
                evidence_refs=["evidence-5", "evidence-6"],
                source_start_block_id="evidence-5",
                source_end_block_id="evidence-6",
            ),
        ]
    return TenderAnalysis(
        status="completed",
        package_type=package_type,
        summary="按招标文件明确分册生成骨架。",
        format_start_block_id="evidence-1",
        format_end_block_id="evidence-6",
        outputs=outputs,
        evidence=_evidence(document),
    )


@dataclass
class FakeReader:
    document: TenderDocument

    def read(self, *, file_name: str, content: bytes) -> TenderDocument:
        return self.document


@dataclass
class FakeRenderer:
    calls: list[TenderAnalysis]

    def render(self, *, document: TenderDocument, analysis: TenderAnalysis):
        self.calls.append(analysis)
        return (
            GeneratedTenderArtifact(
                file_name="骨架.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=b"docx",
            ),
        )


class BoundaryFakeLlm:
    def __init__(
        self,
        document: TenderDocument,
        analysis: TenderAnalysis,
        verification: TenderBoundaryVerification | None = None,
    ) -> None:
        self.document = document
        self.analysis = analysis
        self.verification = verification or TenderBoundaryVerification(
            should_adjust=False,
            reason="边界覆盖格式区域。",
        )
        self.calls: list[type[object]] = []
        self.requests: list[StructuredLlmRequest] = []

    def invoke(self, request: StructuredLlmRequest, output_schema: type[object]):
        self.calls.append(output_schema)
        self.requests.append(request)
        value = self.verification if output_schema is TenderBoundaryVerification else self.analysis
        return StructuredLlmResult(
            value=value,
            model="boundary-fake",
            prompt_version=request.prompt_version,
        )


def test_boundary_pipeline_verifies_single_and_keeps_exact_range() -> None:
    document = _document()
    analysis = _analysis(
        document,
        package_type="single_volume",
        outputs=[
            TenderOutputPlan(
                name="投标文件",
                slug="bid",
                document_label="投标文件",
                evidence_refs=[block.block_id for block in document.blocks],
                source_start_block_id="evidence-1",
                source_end_block_id="evidence-6",
            )
        ],
    )
    llm = BoundaryFakeLlm(document, analysis)
    renderer = FakeRenderer([])

    result = TenderApplication(
        boundary_llm=llm,
        verify_llm=llm,
        reader=FakeReader(document),
        renderer=renderer,
    ).execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))

    assert llm.calls == [TenderAnalysis, TenderBoundaryVerification]
    assert result.analysis.outputs[0].source_start_block_id == "evidence-1"
    assert result.analysis.outputs[0].source_end_block_id == "evidence-6"
    assert len(renderer.calls) == 1


def test_boundary_pipeline_rejects_overlapping_volumes_before_render() -> None:
    document = _document()
    analysis = _analysis(
        document,
        outputs=[
            TenderOutputPlan(
                name="商务技术文件",
                slug="commercial-technical",
                document_label="商务技术文件",
                evidence_refs=["evidence-3"],
                source_start_block_id="evidence-3",
                source_end_block_id="evidence-5",
            ),
            TenderOutputPlan(
                name="报价文件",
                slug="pricing",
                document_label="报价文件",
                evidence_refs=["evidence-5"],
                source_start_block_id="evidence-5",
                source_end_block_id="evidence-6",
            ),
        ],
    )
    renderer = FakeRenderer([])

    with pytest.raises(TenderAnalysisError, match="范围重叠"):
        TenderApplication(
            boundary_llm=BoundaryFakeLlm(document, analysis),
            reader=FakeReader(document),
            renderer=renderer,
        ).execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))

    assert renderer.calls == []


def test_boundary_pipeline_rejects_large_uncovered_gap() -> None:
    document = _document()
    document = TenderDocument(
        file_name=document.file_name,
        content=document.content,
        blocks=document.blocks
        + tuple(
            TenderDocumentBlock(
                block_id=f"evidence-{index}",
                kind="paragraph",
                text=f"未覆盖内容 {index}",
                order=index,
                heading_path=("投标文件格式",),
            )
            for index in range(7, 11)
        ),
        source_text=document.source_text,
    )
    analysis = _analysis(
        document,
        outputs=[
            TenderOutputPlan(
                name="商务技术文件",
                slug="commercial-technical",
                document_label="商务技术文件",
                evidence_refs=["evidence-3"],
                source_start_block_id="evidence-3",
                source_end_block_id="evidence-3",
            ),
            TenderOutputPlan(
                name="报价文件",
                slug="pricing",
                document_label="报价文件",
                evidence_refs=["evidence-10"],
                source_start_block_id="evidence-10",
                source_end_block_id="evidence-10",
            ),
        ],
    ).model_copy(update={"format_end_block_id": "evidence-10"})

    with pytest.raises(TenderAnalysisError, match="未覆盖"):
        TenderApplication(
            boundary_llm=BoundaryFakeLlm(document, analysis),
            reader=FakeReader(document),
            renderer=FakeRenderer([]),
        ).execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_boundary_pipeline_applies_single_boundary_verification_adjustment() -> None:
    document = _document()
    analysis = _analysis(
        document,
        package_type="single_volume",
        outputs=[
            TenderOutputPlan(
                name="投标文件",
                slug="bid",
                document_label="投标文件",
                evidence_refs=["evidence-2", "evidence-3", "evidence-4"],
                source_start_block_id="evidence-2",
                source_end_block_id="evidence-4",
            )
        ],
    )
    verification = TenderBoundaryVerification(
        should_adjust=True,
        reason="格式标题应包含在输出范围内。",
        new_start_block_id="evidence-1",
        new_end_block_id="evidence-6",
    )
    llm = BoundaryFakeLlm(document, analysis, verification)

    result = TenderApplication(
        boundary_llm=llm,
        verify_llm=llm,
        reader=FakeReader(document),
        renderer=FakeRenderer([]),
    ).execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))

    assert result.analysis.format_start_block_id == "evidence-1"
    assert result.analysis.format_end_block_id == "evidence-6"
    assert result.analysis.outputs[0].source_start_block_id == "evidence-1"
    assert result.analysis.outputs[0].source_end_block_id == "evidence-6"
