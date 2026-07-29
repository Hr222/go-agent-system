from __future__ import annotations

import asyncio

import pytest

from app.modules.llm.application.chat import ChatApplication, ChatCommand
from app.modules.llm.application.streaming_chat import StreamingChatApplication
from app.modules.llm.contracts import ChatLlmResult, ChatLlmStreamChunk


class FakeChatLlm:
    def __init__(self, result: ChatLlmResult) -> None:
        self.result = result
        self.requests = []

    def invoke(self, request):  # noqa: ANN001
        self.requests.append(request)
        return self.result


class FakeStreamingChatLlm:
    def __init__(self, chunks: list[ChatLlmStreamChunk]) -> None:
        self.chunks = chunks
        self.requests = []

    def stream(self, request):  # noqa: ANN001
        self.requests.append(request)

        async def chunks():
            for chunk in self.chunks:
                yield chunk

        return chunks()


def test_chat_application_returns_single_turn_result() -> None:
    llm = FakeChatLlm(
        ChatLlmResult(
            content="模型已连接。",
            model="glm-test",
            prompt_version="llm-chat-v1",
            total_tokens=12,
        )
    )
    application = ChatApplication(llm)

    result = application.execute(ChatCommand(message="  你好  "))

    assert result.answer == "模型已连接。"
    assert result.model == "glm-test"
    assert result.prompt_version == "llm-chat-v1"
    assert llm.requests[0].user_prompt == "你好"


def test_chat_application_rejects_empty_message() -> None:
    llm = FakeChatLlm(
        ChatLlmResult(content="不会调用", model="glm-test", prompt_version="llm-chat-v1")
    )

    with pytest.raises(ValueError, match="消息内容不能为空"):
        ChatApplication(llm).execute(ChatCommand(message="   "))


def test_chat_application_rejects_empty_llm_response() -> None:
    llm = FakeChatLlm(ChatLlmResult(content="", model="glm-test", prompt_version="llm-chat-v1"))

    with pytest.raises(RuntimeError, match="空响应"):
        ChatApplication(llm).execute(ChatCommand(message="你好"))


def test_streaming_chat_application_returns_stream_and_normalizes_message() -> None:
    llm = FakeStreamingChatLlm(
        [
            ChatLlmStreamChunk(content="你好"),
            ChatLlmStreamChunk(content="，世界！", model="glm-test"),
        ]
    )

    async def scenario() -> None:
        stream = await StreamingChatApplication(llm).execute(ChatCommand(message="  你好  "))
        chunks = [chunk async for chunk in stream]

        assert [chunk.content for chunk in chunks] == ["你好", "，世界！"]
        assert llm.requests[0].user_prompt == "你好"

    asyncio.run(scenario())


@pytest.mark.parametrize("message", ["", "   ", "\t\n"])
def test_streaming_chat_application_rejects_empty_or_whitespace_message(message: str) -> None:
    llm = FakeStreamingChatLlm([])

    async def scenario() -> None:
        with pytest.raises(ValueError, match="消息内容不能为空"):
            await StreamingChatApplication(llm).execute(ChatCommand(message=message))

    asyncio.run(scenario())
    assert llm.requests == []
