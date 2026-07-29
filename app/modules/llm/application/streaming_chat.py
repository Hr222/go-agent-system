from __future__ import annotations

from collections.abc import AsyncIterator

from app.modules.llm.application.chat import (
    DEFAULT_CHAT_PROMPT_VERSION,
    DEFAULT_CHAT_SYSTEM_PROMPT,
    ChatCommand,
)
from app.modules.llm.contracts import (
    ChatLlmRequest,
    ChatLlmStreamChunk,
    StreamingChatLlmPort,
)


class StreamingChatApplication:
    """编排一次独立的单轮 LLM 流式调用。"""

    def __init__(
        self,
        llm: StreamingChatLlmPort,
        *,
        system_prompt: str = DEFAULT_CHAT_SYSTEM_PROMPT,
        prompt_version: str = DEFAULT_CHAT_PROMPT_VERSION,
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt
        self.prompt_version = prompt_version

    async def execute(self, command: ChatCommand) -> AsyncIterator[ChatLlmStreamChunk]:
        message = command.message.strip()
        if not message:
            raise ValueError("消息内容不能为空。")

        return self.llm.stream(
            request=self._build_request(message),
        )

    def _build_request(self, message: str) -> ChatLlmRequest:
        return ChatLlmRequest(
            system_prompt=self.system_prompt,
            user_prompt=message,
            prompt_version=self.prompt_version,
        )
