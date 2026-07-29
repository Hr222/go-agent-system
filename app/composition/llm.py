"""通用 LLM 能力的 Composition Root。"""

from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.llm.contracts import ChatLlmPort, StreamingChatLlmPort, StructuredLlmPort


def build_chat_llm(client_factory: OpenAICompatibleClientFactory) -> ChatLlmPort:
    """组装通用文本 Chat LLM。"""

    return LangChainGlmChatLlm(client_factory=client_factory)


def build_streaming_chat_llm(
    client_factory: OpenAICompatibleClientFactory,
) -> StreamingChatLlmPort:
    """组装通用文本 Chat LLM 的异步流式能力。"""

    return LangChainGlmChatLlm(client_factory=client_factory)


def build_structured_llm(
    client_factory: OpenAICompatibleClientFactory,
) -> StructuredLlmPort:
    """组装通用结构化 LLM。"""

    return LangChainGlmStructuredLlm(client_factory=client_factory)
