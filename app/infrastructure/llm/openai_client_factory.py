from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from openai import OpenAI

from app.shared.config import Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError


class OpenAICompatibleClientFactory:
    """创建并缓存 OpenAI-compatible Client，供不同 LLM 适配器共享。"""

    def __init__(self, *, configuration: Settings = settings) -> None:
        self.configuration = configuration
        self._client: OpenAI | None = None

    def create_client(self) -> OpenAI:
        """创建或返回当前 Provider 共享的 OpenAI Client。"""

        if self._client is not None:
            return self._client

        if not self.configuration.zhipu_api_key:
            raise ServiceNotConfiguredError(
                "未配置 ZHIPU_API_KEY，无法创建 OpenAI-compatible Client。"
            )

        self._client = OpenAI(
            api_key=self.configuration.zhipu_api_key,
            base_url=self.configuration.zhipu_base_url,
            timeout=self.configuration.zhipu_timeout_seconds,
        )
        return self._client

    def create_chat_model(self, *, model: str) -> ChatOpenAI:
        """基于共享 Client 创建 LangChain Chat Model。"""

        client = self.create_client()
        if not model:
            raise ServiceNotConfiguredError(
                "未配置 ZHIPU_CHAT_MODEL，无法创建 LangChain Chat Model。"
            )

        model_kwargs: dict[str, Any] = {
            "client": client.chat.completions,
            "root_client": client,
            "api_key": self.configuration.zhipu_api_key,
            "base_url": self.configuration.zhipu_base_url,
            "model": model,
            "temperature": self.configuration.zhipu_temperature,
            "timeout": self.configuration.zhipu_timeout_seconds,
        }
        if self.configuration.zhipu_max_tokens is not None:
            model_kwargs["max_tokens"] = self.configuration.zhipu_max_tokens
        return ChatOpenAI(**model_kwargs)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
