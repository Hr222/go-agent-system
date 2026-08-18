from __future__ import annotations

import pytest

from app.infrastructure.llm.langchain_glm_chat_adapter import LangChainGlmChatLlm
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


def _request() -> ChatLlmRequest:
    return ChatLlmRequest(
        system_prompt="你是测试助手。",
        user_prompt="回复连接状态。",
        prompt_version="llm-chat-v1",
    )


def test_langchain_chat_adapter_returns_text_and_usage() -> None:
    model = FakeChatModel(FakeMessage())
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_chat_model="glm-test"),
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


def test_langchain_chat_adapter_preserves_history_roles_and_order() -> None:
    model = FakeChatModel(FakeMessage())
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_chat_model="glm-test"),
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
        configuration=Settings(zhipu_chat_model="glm-test"),
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
        configuration=Settings(zhipu_chat_model="glm-test"),
        chat_model=model,
    )

    async def scenario() -> None:
        result = [chunk async for chunk in adapter.stream(_request())]

        assert [chunk.content for chunk in result] == ["第一段", "完成"]
        assert result[-1].model == "glm-test"
        assert result[-1].prompt_version == "llm-chat-v1"
        assert result[-1].total_tokens == 10
        assert model.messages is not None

    import asyncio

    asyncio.run(scenario())


def test_langchain_chat_adapter_streams_history_messages_in_order() -> None:
    model = FakeStreamingChatModel([FakeMessage()])
    adapter = LangChainGlmChatLlm(
        configuration=Settings(zhipu_chat_model="glm-test"),
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
        configuration=Settings(zhipu_chat_model="glm-test"),
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
