from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel

from app.composition.llm import (
    build_chat_llm,
    build_streaming_chat_llm,
    build_structured_llm,
)
from app.infrastructure.llm import openai_client_factory as factory_module
from app.infrastructure.llm.langchain_deepseek_adapter import LangChainDeepSeekStructuredLlm
from app.infrastructure.llm.langchain_deepseek_chat_adapter import LangChainDeepSeekChatLlm
from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.llm.contracts import ChatLlmRequest, StructuredLlmRequest
from app.shared.config import Settings
from app.shared.exceptions import UpstreamServiceError


class ProbeResult(BaseModel):
    status: str
    message: str


class FakeMessage:
    def __init__(self, content: object, *, reasoning_content: object | None = None) -> None:
        self.content = content
        self.reasoning_content = reasoning_content
        self.usage_metadata = {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
        self.response_metadata: dict[str, object] = {}


class FakeChatModel:
    def __init__(self, response: object) -> None:
        self.response = response
        self.bind_kwargs: dict[str, object] | None = None
        self.messages: object | None = None

    def bind(self, **kwargs: object) -> "FakeChatModel":
        self.bind_kwargs = kwargs
        return self

    def invoke(self, messages: object) -> object:
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def astream(self, messages: object):  # noqa: ANN001
        self.messages = messages
        yield self.response


class FakeRawCompletions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return self.response


class FakeClientFactory:
    def __init__(self, response: object) -> None:
        self.completions = FakeRawCompletions(response)

    def create_client(self) -> object:
        return type("Client", (), {"chat": type("Chat", (), {"completions": self.completions})()})()

    def create_chat_model(self, *, model: str) -> object:
        del model
        return object()


def _deepseek_settings() -> Settings:
    return Settings(
        llm_provider="deepseek",
        deepseek_api_key="test-deepseek-key",
        deepseek_base_url="https://example.com",
        deepseek_chat_model="deepseek-test",
        deepseek_thinking="disabled",
    )


def test_empty_optional_max_tokens_from_env_is_treated_as_unset() -> None:
    configuration = Settings(deepseek_max_tokens="")

    assert configuration.deepseek_max_tokens is None


def test_structured_provider_defaults_to_explicit_output_limit() -> None:
    configuration = _deepseek_settings()

    assert configuration.deepseek_max_tokens == 16_384
    assert Settings(zhipu_resource_chat_model="glm-test").zhipu_max_tokens == 16_384


def _chat_request() -> ChatLlmRequest:
    return ChatLlmRequest("system", "user", "deepseek-chat-v1")


def _structured_request() -> StructuredLlmRequest:
    return StructuredLlmRequest("system", "return JSON", "deepseek-structured-v1")


def test_deepseek_chat_and_streaming_keep_existing_result_contract() -> None:
    model = FakeChatModel(FakeMessage("DeepSeek ready"))
    adapter = LangChainDeepSeekChatLlm(configuration=_deepseek_settings(), chat_model=model)

    result = adapter.invoke(_chat_request())
    assert result.content == "DeepSeek ready"
    assert result.model == "deepseek-test"
    assert result.total_tokens == 8
    assert model.bind_kwargs == {"extra_body": {"thinking": {"type": "disabled"}}}

    async def collect() -> list[object]:
        return [chunk async for chunk in adapter.stream(_chat_request())]

    chunks = asyncio.run(collect())
    assert chunks[0].content == "DeepSeek ready"
    assert chunks[0].model == "deepseek-test"


def test_factory_builds_and_caches_deepseek_client_with_provider_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[dict[str, object]] = []

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr(factory_module, "OpenAI", FakeOpenAI)
    factory = OpenAICompatibleClientFactory(
        configuration=_deepseek_settings(),
        provider="deepseek",
    )

    client = factory.create_client()
    assert factory.create_client() is client
    assert created == [
        {
            "api_key": "test-deepseek-key",
            "base_url": "https://example.com",
            "timeout": 60.0,
            "max_retries": 0,
        }
    ]

    factory.close()


def test_deepseek_structured_disables_thinking_and_excludes_reasoning_content() -> None:
    model = FakeChatModel(
        FakeMessage(
            json.dumps({"status": "ok", "message": "business"}),
            reasoning_content="internal reasoning must not become a field",
        )
    )
    adapter = LangChainDeepSeekStructuredLlm(
        configuration=_deepseek_settings(),
        chat_model=model,
    )

    result = adapter.invoke(_structured_request(), ProbeResult)

    assert result.value == ProbeResult(status="ok", message="business")
    assert model.bind_kwargs == {
        "response_format": {"type": "json_object"},
        "max_tokens": 16_384,
        "extra_body": {"thinking": {"type": "disabled"}},
    }


def test_deepseek_structured_accepts_schema_named_json_wrapper() -> None:
    model = FakeChatModel(
        json.dumps({"probe_result": {"status": "ok", "message": "wrapped"}})
    )
    adapter = LangChainDeepSeekStructuredLlm(
        configuration=_deepseek_settings(),
        chat_model=model,
    )

    result = adapter.invoke(_structured_request(), ProbeResult)

    assert result.value == ProbeResult(status="ok", message="wrapped")


def test_deepseek_raw_request_contains_json_object_and_thinking_payload() -> None:
    response = type(
        "Response",
        (),
        {
            "choices": [
                type(
                    "Choice",
                    (),
                    {
                        "message": type(
                            "Message",
                            (),
                            {
                                "content": json.dumps(
                                    {"status": "ok", "message": "raw"}
                                ),
                                "reasoning_content": "not business data",
                            },
                        )()
                    },
                )()
            ]
        },
    )()
    factory = FakeClientFactory(response)
    adapter = LangChainDeepSeekStructuredLlm(
        configuration=_deepseek_settings(),
        client_factory=factory,
    )

    result = adapter.invoke(_structured_request(), ProbeResult)

    assert result.value.message == "raw"
    assert factory.completions.kwargs is not None
    assert factory.completions.kwargs["response_format"] == {"type": "json_object"}
    assert factory.completions.kwargs["max_tokens"] == 16_384
    assert factory.completions.kwargs["extra_body"] == {
        "thinking": {"type": "disabled"}
    }


@pytest.mark.parametrize(
    "content",
    ["", "not-json", {"status": "ok", "message": {"wrong": "type"}}],
)
def test_deepseek_structured_failures_close_without_guessing(content: object) -> None:
    adapter = LangChainDeepSeekStructuredLlm(
        configuration=_deepseek_settings(),
        chat_model=FakeChatModel(content),
    )

    with pytest.raises(UpstreamServiceError):
        adapter.invoke(_structured_request(), ProbeResult)


def test_composition_selects_both_openai_compatible_providers() -> None:
    glm_factory = OpenAICompatibleClientFactory(
        configuration=Settings(
            zhipu_api_key="glm-key",
            zhipu_resource_chat_model="glm-test",
        )
    )
    deepseek_factory = OpenAICompatibleClientFactory(
        configuration=_deepseek_settings(),
        provider="deepseek",
    )

    assert isinstance(build_chat_llm(glm_factory), LangChainGlmChatLlm)
    assert isinstance(build_streaming_chat_llm(glm_factory), LangChainGlmChatLlm)
    assert isinstance(build_structured_llm(glm_factory), LangChainGlmStructuredLlm)
    assert isinstance(build_chat_llm(deepseek_factory), LangChainDeepSeekChatLlm)
    assert isinstance(build_streaming_chat_llm(deepseek_factory), LangChainDeepSeekChatLlm)
    assert isinstance(build_structured_llm(deepseek_factory), LangChainDeepSeekStructuredLlm)

    glm_factory.close()
    deepseek_factory.close()
