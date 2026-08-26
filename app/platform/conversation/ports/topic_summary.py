from __future__ import annotations

from typing import Protocol


class ConversationTopicSummaryGenerator(Protocol):
    """生成会话首轮话题概括的能力端口。"""

    def generate(self, message: str) -> str | None: ...


__all__ = ["ConversationTopicSummaryGenerator"]
