from __future__ import annotations

from typing import Protocol

from app.modules.conversation.domain.model_context import ModelContextMessage


class ContextMessageCostEstimator(Protocol):
    """估算一条模型上下文消息所占成本单位的可替换端口。"""

    def estimate_cost(self, message: ModelContextMessage) -> int: ...
