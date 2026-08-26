from __future__ import annotations

from dataclasses import dataclass

from app.platform.llm.contracts import ChatLlmPort, ChatLlmRequest

DEFAULT_CHAT_SYSTEM_PROMPT = (
    "你是一个通用中文助手。请直接、清晰地回答用户当前的问题。"
    "当前只处理单轮请求，不假设存在历史会话、知识库证据或外部工具。"
)
DEFAULT_CHAT_PROMPT_VERSION = "llm-chat-v1"


@dataclass(slots=True, frozen=True)
class ChatCommand:
    message: str


@dataclass(slots=True, frozen=True)
class ChatApplicationResult:
    answer: str
    model: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class ChatApplication:
    """编排一次独立的单轮 LLM 调用。"""

    def __init__(
        self,
        llm: ChatLlmPort,
        *,
        system_prompt: str = DEFAULT_CHAT_SYSTEM_PROMPT,
        prompt_version: str = DEFAULT_CHAT_PROMPT_VERSION,
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt
        self.prompt_version = prompt_version

    def execute(self, command: ChatCommand) -> ChatApplicationResult:
        message = command.message.strip()
        if not message:
            raise ValueError("消息内容不能为空。")

        result = self.llm.invoke(
            request=self._build_request(message),
        )
        answer = result.content.strip()
        if not answer:
            raise RuntimeError("LLM 返回了空响应。")

        return ChatApplicationResult(
            answer=answer,
            model=result.model,
            prompt_version=result.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        )

    def _build_request(self, message: str) -> ChatLlmRequest:
        return ChatLlmRequest(
            system_prompt=self.system_prompt,
            user_prompt=message,
            prompt_version=self.prompt_version,
        )
