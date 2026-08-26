from __future__ import annotations

from typing import Protocol

from app.business.online.contracts import AnswerResult
from app.platform.knowledge.ports.read_port import KnowledgeSearchHit


class AnswerGenerator(Protocol):
    """在线应用依赖的回答生成端口。"""

    def answer(self, *, query: str, hits: list[KnowledgeSearchHit]) -> AnswerResult: ...
