from __future__ import annotations

import re

from app.modules.conversation.domain import MAX_TOPIC_SUMMARY_LENGTH


def normalize_topic_summary(value: str | None) -> str | None:
    """将生成器输出收敛为可持久化的单行短文本。"""

    if value is None or not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return None
    return normalized[:MAX_TOPIC_SUMMARY_LENGTH]


class RuleBasedConversationTopicSummaryGenerator:
    """从首条用户消息提取稳定、低成本的话题概括。"""

    def generate(self, message: str) -> str | None:
        normalized = normalize_topic_summary(message)
        if normalized is None:
            return None
        first_sentence = re.split(r"[。！？!?；;]+", normalized, maxsplit=1)[0].strip()
        return normalize_topic_summary(first_sentence) or normalized


__all__ = ["RuleBasedConversationTopicSummaryGenerator", "normalize_topic_summary"]
