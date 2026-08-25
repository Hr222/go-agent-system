from __future__ import annotations

from typing import Any

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.openai_compatible_chat_adapter import OpenAICompatibleChatLlm
from app.infrastructure.llm.request_governance import LlmRequestGovernor
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.shared.config import Settings, settings


class LangChainGlmChatLlm(OpenAICompatibleChatLlm):
    """使用 GLM 的普通文本和流式 Chat 适配器。"""

    def __init__(
        self,
        *,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
        retry_policy: LlmTransientRetryPolicy | None = None,
        request_governor: LlmRequestGovernor | None = None,
    ) -> None:
        super().__init__(
            provider="glm",
            provider_label="GLM",
            configuration=configuration,
            client_factory=client_factory,
            chat_model=chat_model,
            retry_policy=retry_policy,
            request_governor=request_governor,
        )
