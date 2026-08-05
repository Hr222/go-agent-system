from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


@dataclass(slots=True, frozen=True)
class ChatLlmRequest:
    """单轮文本 LLM 调用请求，不暴露具体模型 SDK。"""

    system_prompt: str
    user_prompt: str
    prompt_version: str


@dataclass(slots=True, frozen=True)
class ChatLlmResult:
    """单轮文本调用结果。"""

    content: str
    model: str
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ChatLlmPort(Protocol):
    """通用文本对话能力端口。"""

    def invoke(self, request: ChatLlmRequest) -> ChatLlmResult: ...


@dataclass(slots=True, frozen=True)
class ChatLlmStreamChunk:
    """流式文本片段及可选的结束元数据。"""

    content: str
    model: str | None = None
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class StreamingChatLlmPort(Protocol):
    """单轮文本对话的异步流式能力端口。"""

    def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]: ...


@dataclass(slots=True, frozen=True)
class StructuredLlmRequest:
    """结构化 LLM 调用请求，不暴露具体模型 SDK。"""

    system_prompt: str
    user_prompt: str
    prompt_version: str


@dataclass(slots=True, frozen=True)
class StructuredLlmResult(Generic[StructuredModel]):
    """结构化 LLM 调用结果，保留模型和 Prompt 版本信息。"""

    value: StructuredModel
    model: str
    prompt_version: str
    finish_reason: str | None = None
    usage: Mapping[str, object] | None = None


class StructuredLlmPort(Protocol):
    """通用结构化 LLM 能力端口。"""

    def invoke(
        self,
        request: StructuredLlmRequest,
        output_schema: type[StructuredModel],
    ) -> StructuredLlmResult[StructuredModel]: ...
