from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class KnowledgeWriteResult:
    """知识写入用例可消费的持久化结果。"""

    document_id: int
    version_id: int
    version_seq: int
    version_label: str
    section_count: int
    chunk_count: int


class KnowledgeWritePort(Protocol):
    """入库用例依赖的知识写入端口。

    具体参数仍由入库流水线的内部上下文提供，端口不依赖 HTTP Schema。
    """

    def save_document_version_blocks_sections_and_chunks(
        self,
        **kwargs: object,
    ) -> KnowledgeWriteResult: ...
