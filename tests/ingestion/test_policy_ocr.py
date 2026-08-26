from __future__ import annotations

from pathlib import Path

from app.infrastructure.ocr.tencent_ocr import PolicyOcrService
from app.platform.ingestion.contracts import ParsedBlock, ParsedDocumentResult
from app.shared.config import settings

TEST_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def make_block(
    *,
    block_id: str,
    block_type: str,
    page_no: int | None = None,
    text: str | None = None,
    metadata: dict | None = None,
) -> ParsedBlock:
    return ParsedBlock(
        block_id=block_id,
        order=0,
        page_no=page_no,
        block_type=block_type,
        source="direct",
        text=text,
        metadata=metadata or {},
        layout_hint={},
    )


def make_document(*blocks: ParsedBlock, suspected_scanned: bool = True) -> ParsedDocumentResult:
    normalized_blocks = [
        block.model_copy(update={"order": index}) for index, block in enumerate(blocks)
    ]
    return ParsedDocumentResult(
        parser_status="parsed",
        source_path=str(TEST_FIXTURES_DIR / "scanned.pdf"),
        file_type="pdf",
        suspected_scanned=suspected_scanned,
        blocks=normalized_blocks,
        notes=[],
    )


def test_select_ocr_targets_prefers_page_render_blocks_for_scanned_pdf() -> None:
    service = PolicyOcrService(client=object())
    document = make_document(
        make_block(
            block_id="render-page-1",
            block_type="image",
            page_no=1,
            metadata={"pdf_page_render": True},
        ),
        make_block(
            block_id="embedded-image-1",
            block_type="image",
            page_no=1,
            metadata={"image_bytes": "89504e47"},
        ),
    )

    targets = service._select_ocr_targets(document)

    assert [block.block_id for block in targets] == ["render-page-1"]


def test_select_ocr_targets_supports_standalone_image_documents() -> None:
    service = PolicyOcrService(client=object())
    document = ParsedDocumentResult(
        parser_status="parsed",
        source_path=str(TEST_FIXTURES_DIR / "page-1.png"),
        file_type="image",
        suspected_scanned=True,
        blocks=[
            make_block(
                block_id="image-1",
                block_type="image",
                page_no=1,
                metadata={"image_bytes": "89504e47", "image_name": "page-1.png"},
            )
        ],
        notes=[],
    )

    targets = service._select_ocr_targets(document)

    assert [block.block_id for block in targets] == ["image-1"]


def test_select_ocr_targets_supports_image_only_docx() -> None:
    service = PolicyOcrService(client=object())
    document = ParsedDocumentResult(
        parser_status="parsed",
        source_path=str(TEST_FIXTURES_DIR / "scanned.docx"),
        file_type="docx",
        suspected_scanned=True,
        blocks=[
            make_block(
                block_id="image-1",
                block_type="image",
                metadata={"image_bytes": "89504e47", "image_name": "page-1.png"},
            )
        ],
        notes=[],
    )

    targets = service._select_ocr_targets(document)

    assert [block.block_id for block in targets] == ["image-1"]


def test_process_returns_disabled_result_when_scanned_pdf_needs_ocr(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", False)

    service = PolicyOcrService(client=object())
    document = make_document(
        make_block(
            block_id="render-page-1",
            block_type="image",
            page_no=1,
            metadata={"pdf_page_render": True},
        )
    )

    result = service.process(document, persist=True)

    assert result.applied is False
    assert result.parse_method == "direct"
    assert result.failed_blocks == 1
    assert result.blocks == document.blocks
    assert result.notes == [
        "OCR 已禁用，当前文档保留直接解析结果。",
        "入库模式下需要 OCR 的文档将被后续阶段拦截。",
    ]


def test_process_updates_text_source_and_runtime_metadata_after_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)

    service = PolicyOcrService(client=object())
    monkeypatch.setattr(
        service,
        "_resolve_image_payload",
        lambda source_path, block: (b"fake-image", "image/png"),
    )
    monkeypatch.setattr(
        service,
        "_ocr_image_bytes",
        lambda *args, **kwargs: "扫描件识别后的正文",
    )

    document = make_document(
        make_block(
            block_id="render-page-1",
            block_type="image",
            page_no=1,
            metadata={
                "pdf_page_render": True,
                "image_bytes": "89504e47",
                "image_name": "page-1.png",
                "custom": "keep-me",
            },
        )
    )

    result = service.process(document, persist=False)

    assert result.applied is True
    assert result.parse_method == "ocr"
    assert result.failed_blocks == 0
    assert result.notes == ["OCR 处理完成：成功 1 个图片块，失败 0 个图片块。"]
    assert result.blocks[0].text == "扫描件识别后的正文"
    assert result.blocks[0].source == "ocr"
    assert result.blocks[0].metadata == {
        "image_name": "page-1.png",
        "custom": "keep-me",
    }
