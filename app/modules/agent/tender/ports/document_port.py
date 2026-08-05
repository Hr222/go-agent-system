from __future__ import annotations

from typing import Protocol

from app.modules.agent.tender.contracts import TenderDocument


class TenderDocumentReaderPort(Protocol):
    """读取当前请求招标文件的能力端口。"""

    def read(self, *, file_name: str, content: bytes) -> TenderDocument: ...

