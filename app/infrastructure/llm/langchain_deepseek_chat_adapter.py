from __future__ import annotations

from typing import Any

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.openai_compatible_chat_adapter import OpenAICompatibleChatLlm
from app.shared.config import Settings, settings


class LangChainDeepSeekChatLlm(OpenAICompatibleChatLlm):
    """使用 DeepSeek 的普通文本和流式 Chat 适配器。"""

    def __init__(
        self,
        *,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
    ) -> None:
        super().__init__(
            provider="deepseek",
            provider_label="DeepSeek",
            configuration=configuration,
            client_factory=client_factory,
            chat_model=chat_model,
        )
