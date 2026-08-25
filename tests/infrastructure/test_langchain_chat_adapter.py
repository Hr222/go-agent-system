from __future__ import annotations

import asyncio

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from app.infrastructure.llm.langchain_deepseek_chat_adapter import (
    LangChainDeepSeekChatLlm,
)
from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.modules.llm.contracts import ChatLlmMessage, ChatLlmMessageRole, ChatLlmRequest
from app.shared.config import Settings
from app.shared.exceptions import UpstreamServiceError


class FakeMessage:
    content = "GLM Chat 已连接。"
    usage_metadata = {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10}
    response_metadata = {}


class FakeChatModel:
    def __init__(self, value: object) -> None:
        self.value = value
        self.messages = None
        self.bind_kwargs: dict[str, object] | None = None

    def bind(self, **kwargs: object) -> "FakeChatModel":
        self.bind_kwargs = kwargs
        return self

    def invoke(self, messages: object) -> object:
        self.messages = messages
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeStreamingChatModel(FakeChatModel):
    def __init__(self, chunks: list[object], error: Exception | None = None) -> None:
        super().__init__(chunks)
        self.error = error

    async def astream(self, messages: object):  # noqa: ANN001
        self.messages = messages
        for chunk in self.value:
            yield chunk
        if self.error is not None:
            raise self.error


class FlakyChatModel(FakeChatModel):
    def __init__(self, response: object, failure: Exception) -> None:
        super().__init__(response)
        self.failure = failure
        self.attempts = 0

    def invoke(self, messages: object) -> object:
        self.messages = messages
        self.attempts += 1
        if self.attempts == 1:
            raise self.failure
        return self.value


class RetryBeforeActivityChatModel(FakeChatModel):
    def __init__(self) -> None:
        super().__init__(FakeMessage())
        self.attempts = 0
        self.closed_attempts: list[int] = []

    def astream(self, messages: object):  # noqa: ANN201
        self.messages = messages
        self.attempts += 1
        attempt = self.attempts

        async def generate():
            try:
                if attempt == 1:
                    raise _timeout_error()
                yield self.value
            finally:
                self.closed_attempts.append(attempt)

        return generate()


class FailAfterActivityChatModel(RetryBeforeActivityChatModel):
    def astream(self, messages: object):  # noqa: ANN201
        self.messages = messages
        self.attempts += 1
        attempt = self.attempts

        async def generate():
            try:
                yield self.value
                raise _timeout_error()
            finally:
                self.closed_attempts.append(attempt)

        return generate()


def _request() -> ChatLlmRequest:
    return ChatLlmRequest(
        system_prompt="你是测试助手。",
        user_prompt="回复连接状态。",
        prompt_version="llm-chat-v1",
    )


def _timeout_error() -> APITimeoutError:
    request = httpx.Request("POST", "https://provider.example.com/v1/chat/completions")
    return APITimeoutError(request=request)


def _status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://provider.example.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("provider failure", response=response, body=None)


def _retry_policy(
    *,
    provider: str,
    configuration: Settings,
    waits: list[float],
) -> LlmTransientRetryPolicy:
    return LlmTransientRetryPolicy(
        provider=provider,
        configuration=configuration,
        sleep_fn=waits.append,
        async_sleep_fn=lambda delay: _record_async_wait(waits, delay),
        random_fn=lambda: 0.0,
        clock=lambda: 1.0,
    )


async def _record_async_wait(waits: list[float], delay: float) -> None:
    waits.append(delay)


def test_langchain_chat_adapter_returns_text_and_usage() -> None:
    model = FakeChatModel(FakeMessage())
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=model,
    )

    result = adapter.invoke(_request())

    assert result.content == "GLM Chat 已连接。"
    assert result.model == "glm-test"
    assert result.total_tokens == 10
    assert model.messages is not None
    assert [(message.type, message.content) for message in model.messages] == [
        ("system", "你是测试助手。"),
        ("human", "回复连接状态。"),
    ]
    assert model.bind_kwargs == {"extra_body": {"thinking": {"type": "disabled"}}}


def test_langchain_glm_chat_adapter_uses_coding_profile_thinking() -> None:
    model = FakeChatModel(FakeMessage())
    adapter = LangChainGlmChatLlm(
        configuration=Settings(
            _env_file=None,
            glm_runtime_profile="coding_plan",
            zhipu_coding_chat_model="glm-coding-test",
            zhipu_coding_thinking="low",
        ),
        chat_model=model,
    )

    adapter.invoke(_request())

    assert model.bind_kwargs == {"extra_body": {"thinking": {"type": "low"}}}


def test_langchain_chat_adapter_preserves_history_roles_and_order() -> None:
    model = FakeChatModel(FakeMessage())
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=model,
    )
    request = ChatLlmRequest(
        system_prompt="运行时系统提示。",
        user_prompt="当前用户问题。",
        prompt_version="dialogue-basic-chat-v1",
        history_messages=(
            ChatLlmMessage(ChatLlmMessageRole.SYSTEM, "历史系统提示。"),
            ChatLlmMessage(ChatLlmMessageRole.USER, "历史用户消息。"),
            ChatLlmMessage(ChatLlmMessageRole.ASSISTANT, "历史助手消息。"),
        ),
    )

    adapter.invoke(request)

    assert [(message.type, message.content) for message in model.messages] == [
        ("system", "运行时系统提示。"),
        ("system", "历史系统提示。"),
        ("human", "历史用户消息。"),
        ("ai", "历史助手消息。"),
        ("human", "当前用户问题。"),
    ]


def test_langchain_chat_adapter_maps_provider_failure() -> None:
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=FakeChatModel(RuntimeError("provider unavailable")),
    )

    with pytest.raises(UpstreamServiceError, match="GLM Chat 调用失败"):
        adapter.invoke(_request())


def test_langchain_chat_adapter_streams_chunks_and_final_usage() -> None:
    chunks = [
        FakeMessage(),
        type(
            "FinalMessage",
            (),
            {
                "content": "完成",
                "usage_metadata": {
                    "input_tokens": 4,
                    "output_tokens": 6,
                    "total_tokens": 10,
                },
                "response_metadata": {},
            },
        )(),
    ]
    chunks[0].content = "第一段"
    model = FakeStreamingChatModel(chunks)
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=model,
    )

    async def scenario() -> None:
        result = [chunk async for chunk in adapter.stream(_request())]

        assert [chunk.content for chunk in result] == ["第一段", "完成"]
        assert result[-1].model == "glm-test"
        assert result[-1].prompt_version == "llm-chat-v1"
        assert result[-1].total_tokens == 10
        assert model.messages is not None
        assert model.bind_kwargs == {
            "extra_body": {"thinking": {"type": "disabled"}}
        }

    import asyncio

    asyncio.run(scenario())


def test_langchain_glm_stream_marks_reasoning_as_activity_without_exposing_it() -> None:
    reasoning_chunk = type(
        "ReasoningChunk",
        (),
        {
            "content": "",
            "reasoning_content": "internal reasoning",
            "usage_metadata": {},
            "response_metadata": {},
        },
    )()
    model = FakeStreamingChatModel([reasoning_chunk])
    adapter = LangChainGlmChatLlm(
        configuration=Settings(_env_file=None, zhipu_resource_chat_model="glm-test"),
        chat_model=model,
    )

    async def scenario() -> list[object]:
        return [chunk async for chunk in adapter.stream(_request())]

    chunks = asyncio.run(scenario())

    assert len(chunks) == 1
    assert chunks[0].content == ""
    assert chunks[0].has_upstream_activity is True
    assert "internal reasoning" not in chunks[0].content


def test_langchain_chat_adapter_streams_history_messages_in_order() -> None:
    model = FakeStreamingChatModel([FakeMessage()])
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=model,
    )
    request = ChatLlmRequest(
        system_prompt="运行时系统提示。",
        user_prompt="当前用户问题。",
        prompt_version="dialogue-basic-chat-v1",
        history_messages=(
            ChatLlmMessage(ChatLlmMessageRole.USER, "历史用户消息。"),
            ChatLlmMessage(ChatLlmMessageRole.ASSISTANT, "历史助手消息。"),
        ),
    )

    async def scenario() -> None:
        _ = [chunk async for chunk in adapter.stream(request)]

    import asyncio

    asyncio.run(scenario())

    assert [(message.type, message.content) for message in model.messages] == [
        ("system", "运行时系统提示。"),
        ("human", "历史用户消息。"),
        ("ai", "历史助手消息。"),
        ("human", "当前用户问题。"),
    ]


def test_langchain_chat_adapter_maps_streaming_provider_failure() -> None:
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_resource_chat_model="glm-test"),
        chat_model=FakeStreamingChatModel(
            [FakeMessage()],
            error=RuntimeError("provider unavailable"),
        ),
    )

    async def scenario() -> None:
        with pytest.raises(UpstreamServiceError, match="GLM Chat 流式调用失败"):
            _ = [chunk async for chunk in adapter.stream(_request())]

    import asyncio

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("adapter_type", "provider", "configuration"),
    [
        (
            LangChainGlmChatLlm,
            "glm",
            Settings(
                _env_file=None,
                zhipu_resource_chat_model="glm-test",
                llm_retry_base_backoff_seconds=0.01,
            ),
        ),
        (
            LangChainDeepSeekChatLlm,
            "deepseek",
            Settings(
                _env_file=None,
                llm_provider="deepseek",
                deepseek_chat_model="deepseek-test",
                llm_retry_base_backoff_seconds=0.01,
            ),
        ),
    ],
)
def test_openai_compatible_chat_retries_transient_failure_for_each_provider(
    adapter_type,
    provider: str,
    configuration: Settings,
) -> None:  # noqa: ANN001
    waits: list[float] = []
    model = FlakyChatModel(FakeMessage(), _timeout_error())
    adapter = adapter_type(
        configuration=configuration,
        chat_model=model,
        retry_policy=_retry_policy(
            provider=provider,
            configuration=configuration,
            waits=waits,
        ),
    )

    result = adapter.invoke(_request())

    assert result.content == "GLM Chat 已连接。"
    assert model.attempts == 2
    assert waits == [0.01]


def test_openai_compatible_chat_does_not_retry_client_error() -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-test",
        llm_retry_base_backoff_seconds=0.01,
    )
    waits: list[float] = []
    model = FlakyChatModel(FakeMessage(), _status_error(401))
    adapter = LangChainGlmChatLlm(
        configuration=configuration,
        chat_model=model,
        retry_policy=_retry_policy(
            provider="glm",
            configuration=configuration,
            waits=waits,
        ),
    )

    with pytest.raises(UpstreamServiceError, match="GLM Chat 调用失败"):
        adapter.invoke(_request())

    assert model.attempts == 1
    assert waits == []


def test_openai_compatible_stream_retries_only_before_first_activity() -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-test",
        llm_retry_base_backoff_seconds=0.01,
    )
    waits: list[float] = []
    model = RetryBeforeActivityChatModel()
    adapter = LangChainGlmChatLlm(
        configuration=configuration,
        chat_model=model,
        retry_policy=_retry_policy(
            provider="glm",
            configuration=configuration,
            waits=waits,
        ),
    )

    chunks = asyncio.run(_collect(adapter))

    assert [chunk.content for chunk in chunks] == ["GLM Chat 已连接。"]
    assert model.attempts == 2
    assert model.closed_attempts == [1, 2]
    assert waits == [0.01]


def test_openai_compatible_stream_does_not_retry_after_first_activity() -> None:
    configuration = Settings(
        _env_file=None,
        zhipu_resource_chat_model="glm-test",
        llm_retry_base_backoff_seconds=0.01,
    )
    waits: list[float] = []
    model = FailAfterActivityChatModel()
    adapter = LangChainGlmChatLlm(
        configuration=configuration,
        chat_model=model,
        retry_policy=_retry_policy(
            provider="glm",
            configuration=configuration,
            waits=waits,
        ),
    )

    async def scenario() -> None:
        with pytest.raises(UpstreamServiceError, match="GLM Chat 流式调用失败"):
            _ = [chunk async for chunk in adapter.stream(_request())]

    asyncio.run(scenario())

    assert model.attempts == 1
    assert model.closed_attempts == [1]
    assert waits == []


async def _collect(adapter: LangChainGlmChatLlm) -> list[object]:
    return [chunk async for chunk in adapter.stream(_request())]
