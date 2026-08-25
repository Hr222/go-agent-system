from __future__ import annotations

from typing import Any

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.openai_compatible_structured_adapter import (
    OpenAICompatibleStructuredLlm,
)
from app.infrastructure.llm.request_governance import LlmRequestGovernor
from app.infrastructure.llm.structured_output_normalization import (
    SchemaAwareJsonStructuredOutputNormalizer,
    StructuredOutputNormalizer,
)
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.shared.config import Settings, settings


class LangChainDeepSeekStructuredLlm(OpenAICompatibleStructuredLlm):
    """使用 DeepSeek V4-Flash JSON Object 的结构化 LLM 适配器。"""

    def __init__(
        self,
        *,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
        normalizer: StructuredOutputNormalizer | None = None,
        retry_policy: LlmTransientRetryPolicy | None = None,
        request_governor: LlmRequestGovernor | None = None,
    ) -> None:
        super().__init__(
            provider="deepseek",
            provider_label="DeepSeek",
            configuration=configuration,
            client_factory=client_factory,
            chat_model=chat_model,
            normalizer=normalizer or SchemaAwareJsonStructuredOutputNormalizer(),
            retry_policy=retry_policy,
            request_governor=request_governor,
        )
