"""通用 LLM 能力的 Composition Root。"""

from app.infrastructure.llm.langchain_deepseek_adapter import LangChainDeepSeekStructuredLlm
from app.infrastructure.llm.langchain_deepseek_chat_adapter import LangChainDeepSeekChatLlm
from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.structured_output_normalization import (
    StructuredOutputNormalizer,
    build_default_normalizer_registry,
)
from app.platform.llm.contracts import ChatLlmPort, StreamingChatLlmPort, StructuredLlmPort


def build_chat_llm(client_factory: OpenAICompatibleClientFactory) -> ChatLlmPort:
    """组装通用文本 Chat LLM。"""

    if client_factory.provider == "deepseek":
        return LangChainDeepSeekChatLlm(
            configuration=client_factory.configuration,
            client_factory=client_factory,
        )
    return LangChainGlmChatLlm(client_factory=client_factory)


def build_streaming_chat_llm(
    client_factory: OpenAICompatibleClientFactory,
) -> StreamingChatLlmPort:
    """组装通用文本 Chat LLM 的异步流式能力。"""

    if client_factory.provider == "deepseek":
        return LangChainDeepSeekChatLlm(
            configuration=client_factory.configuration,
            client_factory=client_factory,
        )
    return LangChainGlmChatLlm(client_factory=client_factory)


def build_structured_llm(
    client_factory: OpenAICompatibleClientFactory,
) -> StructuredLlmPort:
    """组装通用结构化 LLM。"""

    provider = client_factory.provider
    normalizer = build_default_normalizer_registry().resolve(
        provider,
        model=client_factory.model,
    )
    configuration = client_factory.configuration
    if provider == "deepseek":
        return LangChainDeepSeekStructuredLlm(
            configuration=configuration,
            client_factory=client_factory,
            normalizer=normalizer,
        )
    return LangChainGlmStructuredLlm(
        configuration=configuration,
        client_factory=client_factory,
        normalizer=normalizer,
    )


def build_structured_output_normalizer(
    *, provider: str = "glm", model: str | None = None
) -> StructuredOutputNormalizer:
    """从 Composition Root 选择 Provider 的结构化输出归一化器。"""

    return build_default_normalizer_registry().resolve(provider, model=model)
