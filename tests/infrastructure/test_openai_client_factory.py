from __future__ import annotations

import logging

import pytest

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
    chat_model = factory.create_chat_model(model="glm-test")

    assert second_client is client
    assert chat_model.root_client is client
    assert chat_model.client is client.chat.completions


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
