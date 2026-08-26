from __future__ import annotations

from typing import Protocol

from app.platform.ingestion.contracts import OcrProcessResult, ParsedDocumentResult


class OcrPort(Protocol):
    """入库流程依赖的 OCR 能力。"""

    def process(self, document: ParsedDocumentResult, *, persist: bool) -> OcrProcessResult: ...
