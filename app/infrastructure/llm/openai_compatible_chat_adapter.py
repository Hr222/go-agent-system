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
from app.shared.config import LlmProviderName, Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class OpenAICompatibleChatLlm(ChatLlmPort, StreamingChatLlmPort):
    """适配任意 OpenAI-compatible Provider 的普通 Chat 能力。"""

    def __init__(
        self,
        *,
        provider: LlmProviderName,
        provider_label: str,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.provider = provider
        self.provider_label = provider_label
        self.provider_config = configuration.llm_provider_config(provider)
        self.model = self.provider_config.model
        if chat_model is not None:
            self._chat_model = chat_model
            return

        if not self.provider_config.model:
            raise ServiceNotConfiguredError(
                f"未配置 {provider_label} Chat 模型，无法执行 LLM 调用。"
            )
        if client_factory is None:
            raise RuntimeError(
                f"{provider_label} Chat Adapter 必须由 Composition Root 注入 Client Factory。"
            )
        self._chat_model = client_factory.create_chat_model(
            model=self.provider_config.model,
        )

    def invoke(self, request: ChatLlmRequest) -> ChatLlmResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", request.system_prompt),
                ("human", request.user_prompt),
            ]
        )

        try:
            response = self._model_for_request().invoke(prompt.format_messages())
        except Exception as exc:
            raise UpstreamServiceError(
                f"{self.provider_label} Chat 调用失败"
                f"（Prompt 版本：{request.prompt_version}）：{exc}"
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
        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", request.system_prompt),
                    ("human", request.user_prompt),
                ]
            )

            try:
                async for response in self._model_for_request().astream(
                    prompt.format_messages()
                ):
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
                    f"{self.provider_label} Chat 流式调用失败"
                    f"（Prompt 版本：{request.prompt_version}）：{exc}"
                ) from exc

        return generate()

    def _model_for_request(self) -> Any:
        if self.provider_config.thinking is None:
            return self._chat_model
        return self._chat_model.bind(
            extra_body={"thinking": {"type": self.provider_config.thinking}}
        )


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
