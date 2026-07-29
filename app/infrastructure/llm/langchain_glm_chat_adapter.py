from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.llm.contracts import (
    ChatLlmPort,
    ChatLlmRequest,
    ChatLlmResult,
    ChatLlmStreamChunk,
    StreamingChatLlmPort,
)
from app.shared.config import Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class LangChainGlmChatLlm(ChatLlmPort, StreamingChatLlmPort):
    """使用 GLM 的 LangChain 文本调用适配器。"""

    def __init__(
        self,
        *,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.model = configuration.zhipu_chat_model
        if chat_model is not None:
            self._chat_model = chat_model
            return

        if not configuration.zhipu_chat_model:
            raise ServiceNotConfiguredError(
                "未配置 ZHIPU_CHAT_MODEL，无法执行 LLM Chat 调用。"
            )
        if client_factory is None:
            raise RuntimeError(
                "LangChain GLM Chat Adapter 必须由 Composition Root 注入 Client Factory。"
            )
        self._chat_model = client_factory.create_chat_model(
            model=configuration.zhipu_chat_model,
        )

    def invoke(self, request: ChatLlmRequest) -> ChatLlmResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", request.system_prompt),
                ("human", request.user_prompt),
            ]
        )

        try:
            response = self._chat_model.invoke(prompt.format_messages())
        except Exception as exc:
            raise UpstreamServiceError(
                f"GLM Chat 调用失败（Prompt 版本：{request.prompt_version}）：{exc}"
            ) from exc

        content = _message_content(response)
        usage = _message_usage(response)
        return ChatLlmResult(
            content=content,
            model=self.model or "unknown",
            prompt_version=request.prompt_version,
            input_tokens=usage[0],
            output_tokens=usage[1],
            total_tokens=usage[2],
        )

    def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]:
        """使用 LangChain 原生异步流返回内部流式片段。"""

        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", request.system_prompt),
                    ("human", request.user_prompt),
                ]
            )

            try:
                async for response in self._chat_model.astream(prompt.format_messages()):
                    usage = _message_usage(response)
                    yield ChatLlmStreamChunk(
                        content=_message_content(response),
                        model=self.model or "unknown",
                        prompt_version=request.prompt_version,
                        input_tokens=usage[0],
                        output_tokens=usage[1],
                        total_tokens=usage[2],
                    )
            except Exception as exc:
                raise UpstreamServiceError(
                    f"GLM Chat 流式调用失败（Prompt 版本：{request.prompt_version}）：{exc}"
                ) from exc

        return generate()


def _message_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "").strip()
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
    return str(content or "")


def _message_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    usage = usage_metadata or response_metadata.get("token_usage") or {}

    input_tokens = _optional_int(usage.get("input_tokens", usage.get("prompt_tokens")))
    output_tokens = _optional_int(usage.get("output_tokens", usage.get("completion_tokens")))
    total_tokens = _optional_int(usage.get("total_tokens"))
    return input_tokens, output_tokens, total_tokens


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
