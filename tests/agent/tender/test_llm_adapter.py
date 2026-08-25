from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from app.infrastructure.llm.langchain_glm_adapter import LangChainGlmStructuredLlm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.agent.tender.ports.llm_port import StructuredLlmRequest
from app.shared.config import Settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class ProbeResult(BaseModel):
    status: str
    message: str


class FakeStructuredModel:
    def __init__(self, value: object) -> None:
        self.value = value
        self.messages: object | None = None

    def invoke(self, messages: object) -> object:
        self.messages = messages
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeChatModel:
    def __init__(self, value: object) -> None:
        self.structured_model = FakeStructuredModel(value)
        self.bind_kwargs: dict[str, object] | None = None

    def bind(self, **kwargs: object) -> FakeStructuredModel:
        self.bind_kwargs = kwargs
        return self.structured_model


class FakeRawCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return type(
            "Response",
            (),
            {"content": json.dumps({"status": "ok", "message": "raw client ready"})},
        )()


class FakeOpenAiChatCompletion:
    choices = [
        type(
            "Choice",
            (),
            {
                "message": type(
                    "Message",
                    (),
                    {"content": json.dumps({"status": "ok", "message": "openai shape"})},
                )()
            },
        )()
    ]


class FakeRawClient:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": FakeRawCompletions()})()


class FakeClientFactory:
    def __init__(self) -> None:
        self.client = FakeRawClient()

    def create_chat_model(self, *, model: str) -> object:
        return object()

    def create_client(self) -> FakeRawClient:
        return self.client


def _request() -> StructuredLlmRequest:
    return StructuredLlmRequest(
        system_prompt="你是技术验证助手。",
        user_prompt="返回固定的结构化验证结果。",
        prompt_version="f1-llm-probe-v1",
    )


def test_langchain_glm_adapter_returns_validated_structured_result() -> None:
    fake_model = FakeChatModel(json.dumps({"status": "ok", "message": "GLM adapter ready"}))
    adapter = LangChainGlmStructuredLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=fake_model,
    )

    result = adapter.invoke(_request(), ProbeResult)

    assert result.value == ProbeResult(status="ok", message="GLM adapter ready")
    assert result.model == "glm-test"
    assert result.prompt_version == "f1-llm-probe-v1"
    assert fake_model.bind_kwargs == {
        "response_format": {"type": "json_object"},
        "max_tokens": 16_384,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    assert fake_model.structured_model.messages is not None


def test_langchain_glm_adapter_maps_model_failures() -> None:
    adapter = LangChainGlmStructuredLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=FakeChatModel(RuntimeError("provider unavailable")),
    )

    with pytest.raises(UpstreamServiceError, match="GLM 结构化调用失败"):
        adapter.invoke(_request(), ProbeResult)


def test_langchain_glm_adapter_rejects_missing_configuration() -> None:
    with pytest.raises(ServiceNotConfiguredError, match="ZHIPU_API_KEY"):
        LangChainGlmStructuredLlm(
            configuration=Settings(zhipu_api_key=None, zhipu_resource_chat_model="glm-test"),
            client_factory=OpenAICompatibleClientFactory(
                configuration=Settings(
                    zhipu_api_key=None,
                    zhipu_resource_chat_model="glm-test",
                )
            ),
        )


def test_langchain_glm_adapter_maps_human_role_for_raw_json_object_call() -> None:
    factory = FakeClientFactory()
    adapter = LangChainGlmStructuredLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        client_factory=factory,
    )

    result = adapter.invoke(_request(), ProbeResult)

    assert result.value == ProbeResult(status="ok", message="raw client ready")
    assert factory.client.chat.completions.kwargs is not None
    assert [
        message["role"] for message in factory.client.chat.completions.kwargs["messages"]
    ] == ["system", "user"]
    assert factory.client.chat.completions.kwargs["response_format"] == {
        "type": "json_object"
    }


def test_langchain_glm_adapter_parses_openai_chat_completion_shape() -> None:
    factory = FakeClientFactory()

    def create(**kwargs: object) -> object:
        del kwargs
        return FakeOpenAiChatCompletion()

    factory.client.chat.completions.create = create
    adapter = LangChainGlmStructuredLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        client_factory=factory,
    )

    result = adapter.invoke(_request(), ProbeResult)

    assert result.value.message == "openai shape"
