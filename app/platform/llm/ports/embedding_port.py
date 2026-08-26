from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class TextEmbeddingPort(Protocol):
    """面向应用模块的纯文本向量生成能力。"""

    def embed_text(self, text: str) -> list[float]: ...

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...
