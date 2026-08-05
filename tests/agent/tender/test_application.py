from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderDocument,
    TenderDocumentBlock,
    TenderGenerateSkeletonCommand,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.modules.agent.tender.errors import TenderAnalysisError, TenderRenderError
from app.modules.llm.contracts import StructuredLlmRequest, StructuredLlmResult
from app.shared.exceptions import UpstreamServiceError


def _document() -> TenderDocument:
    blocks = (
        TenderDocumentBlock(
            block_id="evidence-1",
            kind="paragraph",
            text="投标文件格式",
        ),
        TenderDocumentBlock(
            block_id="evidence-2",
            kind="paragraph",
            text="技术标",
        ),
    )
    return TenderDocument(
        file_name="招标文件.docx",
        content=b"docx",
        blocks=blocks,
        source_text="[evidence_id=evidence-1] 投标文件格式",
    )


def _analysis(package_type: str = "single_volume") -> TenderAnalysis:
    output_count = 1 if package_type == "single_volume" else 2
    outputs = [
        TenderOutputPlan(
            name="投标文件" if output_count == 1 else f"第{index}卷",
            slug=f"volume-{index}",
            document_label="投标文件",
            evidence_refs=["evidence-1"],
        )
        for index in range(1, output_count + 1)
    ]
    return TenderAnalysis(
        status="completed",
        package_type=package_type,
        summary="根据招标文件生成骨架。",
        outputs=outputs,
        evidence=[
            TenderSourceEvidence(
                evidence_id="evidence-1",
                location="第一章",
                quote="投标文件格式",
            )
        ],
    )


@dataclass
class FakeReader:
    document: TenderDocument
    calls: int = 0

    def read(self, *, file_name: str, content: bytes) -> TenderDocument:
        self.calls += 1
        return self.document


@dataclass
class FakeLlm:
    analysis: TenderAnalysis | Exception
    calls: list[StructuredLlmRequest]

    def invoke(self, request: StructuredLlmRequest, output_schema: object) -> StructuredLlmResult:
        self.calls.append(request)
        if isinstance(self.analysis, Exception):
            raise self.analysis
        return StructuredLlmResult(
            value=self.analysis,
            model="fake-model",
            prompt_version=request.prompt_version,
        )


@dataclass
class FakeRenderer:
    calls: list[tuple[TenderDocument, TenderAnalysis]]

    def render(
        self, *, document: TenderDocument, analysis: TenderAnalysis
    ) -> tuple[GeneratedTenderArtifact, ...]:
        self.calls.append((document, analysis))
        return (
            GeneratedTenderArtifact(
                file_name="投标文件.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=b"generated",
            ),
        )


def test_tender_application_orchestrates_reader_llm_and_renderer() -> None:
    reader = FakeReader(_document())
    llm = FakeLlm(_analysis(), [])
    renderer = FakeRenderer([])
    application = TenderApplication(llm=llm, reader=reader, renderer=renderer)

    result = application.execute(
        TenderGenerateSkeletonCommand(
            file_name="招标文件.docx",
            content=b"source",
            user_focus="关注投标文件分线",
        )
    )

    assert reader.calls == 1
    assert len(llm.calls) == 1
    assert "关注投标文件分线" in llm.calls[0].user_prompt
    assert renderer.calls[0][1].package_type == "single_volume"
    assert result.model == "fake-model"
    assert result.artifacts[0].content == b"generated"


def test_tender_application_accepts_multi_volume_analysis() -> None:
    renderer = FakeRenderer([])
    application = TenderApplication(
        llm=FakeLlm(_analysis("multi_volume"), []),
        reader=FakeReader(_document()),
        renderer=renderer,
    )

    result = application.execute(
        TenderGenerateSkeletonCommand(file_name="招标文件.docx", content=b"source")
    )

    assert result.analysis.package_type == "multi_volume"
    assert len(result.analysis.outputs) == 2


@pytest.mark.parametrize(
    "analysis",
    [
        _analysis("multi_volume").model_copy(update={"outputs": []}),
        _analysis("single_volume").model_copy(
            update={
                "outputs": [
                    TenderOutputPlan(
                        name="技术标",
                        slug="technical",
                        document_label="技术标",
                    ),
                    TenderOutputPlan(
                        name="商务标",
                        slug="commercial",
                        document_label="商务标",
                    ),
                ]
            }
        ),
    ],
)
def test_tender_application_rejects_inconsistent_output_count(analysis: TenderAnalysis) -> None:
    application = TenderApplication(
        llm=FakeLlm(analysis, []),
        reader=FakeReader(_document()),
        renderer=FakeRenderer([]),
    )

    with pytest.raises(TenderAnalysisError):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_tender_application_preserves_upstream_failure_boundary() -> None:
    application = TenderApplication(
        llm=FakeLlm(UpstreamServiceError("provider failed"), []),
        reader=FakeReader(_document()),
        renderer=FakeRenderer([]),
    )

    with pytest.raises(UpstreamServiceError):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_tender_application_rejects_unknown_source_evidence() -> None:
    analysis = _analysis().model_copy(
        update={
            "outputs": [
                _analysis().outputs[0].model_copy(update={"evidence_refs": ["missing-evidence"]})
            ]
        }
    )
    application = TenderApplication(
        llm=FakeLlm(analysis, []),
        reader=FakeReader(_document()),
        renderer=FakeRenderer([]),
    )

    with pytest.raises(TenderAnalysisError, match="不存在的证据"):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))


def test_tender_application_maps_renderer_failure() -> None:
    class FailingRenderer:
        def render(self, *, document: TenderDocument, analysis: TenderAnalysis) -> object:
            raise ValueError("renderer failed")

    application = TenderApplication(
        llm=FakeLlm(_analysis(), []),
        reader=FakeReader(_document()),
        renderer=FailingRenderer(),
    )

    with pytest.raises(TenderRenderError, match="骨架文件生成失败"):
        application.execute(TenderGenerateSkeletonCommand("招标文件.docx", b"source"))
