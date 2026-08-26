from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import fitz

from app.platform.ingestion.pipeline.scan_service import PolicyIngestionService

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "ocr"
    / "classify_sample_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("classify_sample_inventory", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def build_pdf(path: Path, pages: list[str | None]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(str(path))
    document.close()


def test_analyze_pdf_text_marks_text_and_mixed_and_scanned(tmp_path: Path) -> None:
    text_pdf = tmp_path / "text.pdf"
    mixed_pdf = tmp_path / "mixed.pdf"
    scanned_pdf = tmp_path / "scanned.pdf"

    build_pdf(text_pdf, ["hello world", "second page"])
    build_pdf(mixed_pdf, ["hello world", None])
    build_pdf(scanned_pdf, [None, None])

    text_signal = MODULE.analyze_pdf_text(text_pdf, sample_pages=2)
    mixed_signal = MODULE.analyze_pdf_text(mixed_pdf, sample_pages=2)
    scanned_signal = MODULE.analyze_pdf_text(scanned_pdf, sample_pages=2)

    assert text_signal.pdf_kind == "text"
    assert mixed_signal.pdf_kind == "mixed"
    assert scanned_signal.pdf_kind == "scanned"


def test_classify_file_routes_pipeline_and_business_labels(tmp_path: Path) -> None:
    service = PolicyIngestionService()
    root = tmp_path / "samples"
    root.mkdir()

    charter_pdf = root / "示例章程" / "最新章程.pdf"
    charter_pdf.parent.mkdir(parents=True)
    certificate_image = root / "示例证书" / "示例资质证书.png"
    certificate_image.parent.mkdir(parents=True)
    logo_png = root / "示例文件" / "示例logo.png"
    logo_png.parent.mkdir(parents=True)

    build_pdf(charter_pdf, ["章程正文"])
    certificate_image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    logo_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    charter_item = MODULE.classify_file(
        root=root,
        path=charter_pdf,
        service=service,
        pdf_sample_pages=2,
    )
    certificate_item = MODULE.classify_file(
        root=root,
        path=certificate_image,
        service=service,
        pdf_sample_pages=2,
    )
    logo_item = MODULE.classify_file(
        root=root,
        path=logo_png,
        service=service,
        pdf_sample_pages=2,
    )

    assert charter_item.pipeline_bucket == "direct_parse"
    assert charter_item.knowledge_route == "rag_text"
    assert charter_item.rag_suitability == "high"

    assert certificate_item.pipeline_bucket == "ocr"
    assert certificate_item.knowledge_route == "structured_fields"
    assert certificate_item.rag_suitability == "low"

    assert logo_item.pipeline_bucket == "exclude"
    assert logo_item.knowledge_route == "exclude_low_value"
    assert logo_item.rag_suitability == "low"


def test_classify_file_marks_org_chart_doc_as_structured_medium(tmp_path: Path) -> None:
    service = PolicyIngestionService()
    root = tmp_path / "samples"
    root.mkdir()

    doc_path = root / "示例组织架构" / "示例组织架构图.doc"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_bytes(b"legacy-doc")

    item = MODULE.classify_file(
        root=root,
        path=doc_path,
        service=service,
        pdf_sample_pages=2,
    )

    assert item.pipeline_bucket == "convert_doc_to_docx"
    assert item.knowledge_route == "structured_fields"
    assert item.rag_suitability == "medium"
