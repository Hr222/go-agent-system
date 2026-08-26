from __future__ import annotations

from pathlib import Path

from app.platform.ingestion.contracts import PolicyScanRequest
from app.platform.ingestion.domain import PolicyIntakePolicy
from app.platform.ingestion.pipeline.scan_service import PolicyIngestionService
from app.platform.ingestion.pipeline.steps.policy_parser import PolicyParserService


def test_policy_intake_policy_allows_doc_and_image_inputs() -> None:
    policy = PolicyIntakePolicy()

    doc_decision = policy.decide(
        file_name="人事管理制度.doc",
        extension=".doc",
        size_bytes=1024,
    )
    image_decision = policy.decide(
        file_name="人事管理制度-扫描件.png",
        extension=".png",
        size_bytes=2048,
    )

    assert doc_decision.is_allowed is True
    assert doc_decision.needs_normalization is True
    assert doc_decision.recommended_parse_method == "doc"
    assert image_decision.is_allowed is True
    assert image_decision.recommended_parse_method == "image"


def test_scan_candidates_marks_doc_and_scanned_pdf_and_image_as_include(
    tmp_path: Path,
) -> None:
    doc_path = tmp_path / "制度样本.doc"
    pdf_path = tmp_path / "制度样本-扫描.pdf"
    image_path = tmp_path / "制度样本-页1.png"
    docx_path = tmp_path / "制度样本.docx"

    doc_path.write_bytes(b"legacy-doc")
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    docx_path.write_bytes(b"docx")

    response = PolicyIngestionService().scan_candidates(
        PolicyScanRequest(source_root=str(tmp_path), limit=10)
    )

    candidates = {item.file_name: item for item in response.candidates}

    assert candidates["制度样本.doc"].recommended_action == "include"
    assert candidates["制度样本.doc"].parse_method == "doc"
    assert candidates["制度样本-扫描.pdf"].recommended_action == "include"
    assert candidates["制度样本-扫描.pdf"].parse_method == "ocr"
    assert candidates["制度样本-页1.png"].recommended_action == "include"
    assert candidates["制度样本-页1.png"].parse_method == "ocr"
    assert candidates["制度样本.docx"].recommended_action == "include"
    assert candidates["制度样本.docx"].parse_method == "direct"


def test_parse_image_builds_single_image_block_for_ocr(tmp_path: Path) -> None:
    image_path = tmp_path / "制度扫描页.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    result = PolicyParserService().parse_document(
        source_path=str(image_path),
        parse_method="direct",
    )

    assert result.file_type == "image"
    assert result.suspected_scanned is True
    assert len(result.blocks) == 1
    assert result.blocks[0].block_type == "image"
    assert result.blocks[0].metadata["image_name"] == "制度扫描页.png"
    assert result.blocks[0].metadata["image_bytes"].startswith("89504e47")
