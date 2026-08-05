from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from openai import OpenAI

from app.shared.config import LlmProviderConfig, LlmProviderName, Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError
from app.shared.logging import get_logger

logger = get_logger("app.infrastructure.llm.openai_compatible")


class OpenAICompatibleClientFactory:
    """创建并缓存 OpenAI-compatible Client，供不同 LLM 适配器共享。"""

    def __init__(
        self,
        *,
        configuration: Settings = settings,
        provider: LlmProviderName = "glm",
    ) -> None:
        self.configuration = configuration
        self.provider_config: LlmProviderConfig = configuration.llm_provider_config(provider)
        self._client: OpenAI | None = None

    @property
    def provider(self) -> LlmProviderName:
        return self.provider_config.provider

    @property
    def model(self) -> str | None:
        return self.provider_config.model

    def create_client(self) -> OpenAI:
        """创建或返回当前 Provider 共享的 OpenAI Client。"""

        if self._client is not None:
            return self._client

        if not self.provider_config.api_key:
            raise ServiceNotConfiguredError(
                f"未配置 {_api_key_name(self.provider)}，无法创建 "
                "OpenAI-compatible Client。"
            )

        logger.info(
            "llm client create provider=%s base_url=%s model=%s timeout_seconds=%s "
            "api_key_configured=%s",
            self.provider,
            _safe_base_url(self.provider_config.base_url),
            self.provider_config.model or "unknown",
            self.provider_config.timeout_seconds,
            True,
        )
        self._client = OpenAI(
            api_key=self.provider_config.api_key,
            base_url=self.provider_config.base_url,
            timeout=self.provider_config.timeout_seconds,
            max_retries=0,
        )
        return self._client

    def create_chat_model(self, *, model: str) -> ChatOpenAI:
        """基于共享 Client 创建 LangChain Chat Model。"""

        client = self.create_client()
        if not model:
            raise ServiceNotConfiguredError(
                f"未配置 {self.provider.upper()} 模型，无法创建 LangChain Chat Model。"
            )

        model_kwargs: dict[str, Any] = {
            "client": client.chat.completions,
            "root_client": client,
            "api_key": self.provider_config.api_key,
            "base_url": self.provider_config.base_url,
            "model": model,
            "temperature": self.provider_config.temperature,
            "timeout": self.provider_config.timeout_seconds,
        }
        if self.provider_config.max_tokens is not None:
            model_kwargs["max_tokens"] = self.provider_config.max_tokens
        return ChatOpenAI(**model_kwargs)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _safe_base_url(base_url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
        return "<invalid>"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.hostname}{port}{path}"


def _api_key_name(provider: LlmProviderName) -> str:
    return "ZHIPU_API_KEY" if provider == "glm" else "DEEPSEEK_API_KEY"
