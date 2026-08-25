from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.infrastructure.llm import openai_client_factory as factory_module
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.shared.config import Settings
from app.shared.exceptions import ServiceNotConfiguredError


def _configuration() -> Settings:
    return Settings(
        zhipu_api_key="test-key",
        zhipu_base_url="https://example.com/v1",
        zhipu_chat_model="glm-test",
    )


def test_factory_caches_one_openai_client_for_direct_and_langchain_adapters() -> None:
    factory = OpenAICompatibleClientFactory(configuration=_configuration())

    client = factory.create_client()
    second_client = factory.create_client()
    async_client = factory.create_async_client()
    chat_model = factory.create_chat_model(model="glm-test")

    assert second_client is client
    assert chat_model.root_client is client
    assert chat_model.client is client.chat.completions
    assert chat_model.root_async_client is async_client
    assert chat_model.async_client is async_client.chat.completions
    assert chat_model.max_retries == 0
    asyncio.run(factory.aclose())


@pytest.mark.parametrize(
    ("provider", "configuration", "expected_kwargs"),
    [
        (
            "glm",
            Settings(
                _env_file=None,
                zhipu_api_key="glm-key",
                zhipu_resource_base_url="https://glm.example.com/api/paas/v4",
                zhipu_resource_timeout_seconds=42.5,
            ),
            {
                "api_key": "glm-key",
                "base_url": "https://glm.example.com/api/paas/v4",
                "timeout": 42.5,
                "max_retries": 0,
            },
        ),
        (
            "deepseek",
            Settings(
                _env_file=None,
                deepseek_api_key="deepseek-key",
                deepseek_base_url="https://deepseek.example.com/v1",
                deepseek_timeout_seconds=18.0,
            ),
            {
                "api_key": "deepseek-key",
                "base_url": "https://deepseek.example.com/v1",
                "timeout": 18.0,
                "max_retries": 0,
            },
        ),
    ],
)
def test_factory_builds_sync_and_async_clients_with_identical_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    configuration: Settings,
    expected_kwargs: dict[str, object],
) -> None:
    class SyncClient:
        instances: list[SyncClient] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=object())
            self.close = Mock()
            self.instances.append(self)

    class AsyncClient:
        instances: list[AsyncClient] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=object())
            self.close = AsyncMock()
            self.instances.append(self)

    monkeypatch.setattr(factory_module, "OpenAI", SyncClient)
    monkeypatch.setattr(factory_module, "AsyncOpenAI", AsyncClient)
    factory = OpenAICompatibleClientFactory(
        configuration=configuration,
        provider=provider,  # type: ignore[arg-type]
    )

    sync_client = factory.create_client()
    async_client = factory.create_async_client()

    assert factory.create_client() is sync_client
    assert factory.create_async_client() is async_client
    assert sync_client.kwargs == expected_kwargs
    assert async_client.kwargs == expected_kwargs
    assert len(SyncClient.instances) == 1
    assert len(AsyncClient.instances) == 1


def test_factory_aclose_releases_sync_and_async_clients() -> None:
    factory = OpenAICompatibleClientFactory(configuration=_configuration())
    sync_client = SimpleNamespace(close=Mock())
    async_client = SimpleNamespace(close=AsyncMock())
    factory._client = sync_client  # type: ignore[assignment]
    factory._async_client = async_client  # type: ignore[assignment]

    asyncio.run(factory.aclose())

    sync_client.close.assert_called_once_with()
    async_client.close.assert_awaited_once_with()
    assert factory._client is None
    assert factory._async_client is None


def test_factory_rejects_missing_glm_api_key() -> None:
    factory = OpenAICompatibleClientFactory(
        configuration=Settings(zhipu_api_key=None, zhipu_chat_model="glm-test")
    )

    with pytest.raises(ServiceNotConfiguredError, match="ZHIPU_API_KEY"):
        factory.create_client()


def test_factory_exposes_selected_glm_runtime_profile(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_api_key="test-key",
        glm_runtime_profile="coding_plan",
        zhipu_coding_base_url="https://coding.example.com/v1",
        zhipu_coding_chat_model="coding-model",
    )
    factory = OpenAICompatibleClientFactory(configuration=configuration)

    assert factory.provider_config.runtime_profile == "coding_plan"
    assert factory.provider_config.base_url == "https://coding.example.com/v1"
    assert factory.provider_config.model == "coding-model"

    caplog.set_level(logging.INFO, logger="app.infrastructure.llm.openai_compatible")
    factory.create_client()

    assert "runtime_profile=coding_plan" in caplog.text
    assert "test-key" not in caplog.text
    factory.close()
