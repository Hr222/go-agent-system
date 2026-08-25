from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.transient_retry import LlmTransientRetryPolicy
from app.modules.llm.contracts import (
    ChatLlmMessage,
    ChatLlmMessageRole,
    ChatLlmPort,
    ChatLlmRequest,
    ChatLlmResult,
    ChatLlmStreamChunk,
    StreamingChatLlmPort,
)
from app.shared.config import LlmProviderName, Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class OpenAICompatibleChatLlm(ChatLlmPort, StreamingChatLlmPort):
    """适配任意 OpenAI-compatible Provider 的普通 Chat 能力。"""

    def __init__(
        self,
        *,
        provider: LlmProviderName,
        provider_label: str,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
        retry_policy: LlmTransientRetryPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.provider_label = provider_label
        self.provider_config = configuration.llm_provider_config(provider)
        self.model = self.provider_config.model
        self._stream_first_activity_timeout_seconds = (
            configuration.llm_stream_first_token_timeout_seconds
        )
        self._retry_policy = retry_policy or LlmTransientRetryPolicy(
            provider=provider,
            configuration=configuration,
        )
        if chat_model is not None:
            self._chat_model = chat_model
            return

        if not self.provider_config.model:
            raise ServiceNotConfiguredError(
                f"未配置 {provider_label} Chat 模型，无法执行 LLM 调用。"
            )
        if client_factory is None:
            raise RuntimeError(
                f"{provider_label} Chat Adapter 必须由 Composition Root 注入 Client Factory。"
            )
        self._chat_model = client_factory.create_chat_model(
            model=self.provider_config.model,
        )

    def invoke(self, request: ChatLlmRequest) -> ChatLlmResult:
        try:
            messages = _request_messages(request)
            response = self._retry_policy.execute(
                lambda: self._model_for_request().invoke(messages)
            )
        except Exception as exc:
            raise UpstreamServiceError(
                f"{self.provider_label} Chat 调用失败"
                f"（Prompt 版本：{request.prompt_version}）：{exc}"
            ) from exc

        content = _message_content(response)
        usage = _message_usage(response)
        return ChatLlmResult(
            content=content,
            model=self.model or "unknown",
            prompt_version=request.prompt_version,
            input_tokens=usage[0],
            output_tokens=usage[1],
            total_tokens=usage[2],
        )

    def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]:
        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            messages = _request_messages(request)
            retry_session = self._retry_policy.new_session()
            stream: AsyncIterator[Any] | None = None
            try:
                for attempt in range(1, self._retry_policy.max_attempts + 1):
                    try:
                        stream = self._model_for_request().astream(messages)
                        first_chunk = await _first_activity_chunk(
                            stream,
                            request=request,
                            timeout_seconds=self._stream_first_activity_timeout_seconds,
                            model=self.model or "unknown",
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        await _close_stream(stream)
                        stream = None
                        if await retry_session.retry_after_async_failure(
                            error,
                            attempt=attempt,
                        ):
                            continue
                        raise
                    break
                else:
                    raise RuntimeError("LLM 流式重试循环在未创建流时结束。")

                yield first_chunk
                async for response in stream:
                    yield _stream_chunk(
                        response,
                        model=self.model or "unknown",
                        prompt_version=request.prompt_version,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise UpstreamServiceError(
                    f"{self.provider_label} Chat 流式调用失败"
                    f"（Prompt 版本：{request.prompt_version}）：{exc}"
                ) from exc
            finally:
                await _close_stream(stream)

        return generate()

    def _model_for_request(self) -> Any:
        if self.provider_config.thinking is None:
            return self._chat_model
        return self._chat_model.bind(
            extra_body={"thinking": {"type": self.provider_config.thinking}}
        )


async def _first_activity_chunk(
    stream: AsyncIterator[Any],
    *,
    request: ChatLlmRequest,
    timeout_seconds: float,
    model: str,
) -> ChatLlmStreamChunk:
    """在单次 Provider 尝试内等待正文或 reasoning activity。"""

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError
        try:
            response = await asyncio.wait_for(anext(stream), timeout=remaining)
        except StopAsyncIteration as error:
            raise RuntimeError("LLM returned an empty response.") from error
        chunk = _stream_chunk(
            response,
            model=model,
            prompt_version=request.prompt_version,
        )
        if chunk.has_upstream_activity or chunk.content.strip():
            return chunk


def _stream_chunk(
    response: Any,
    *,
    model: str,
    prompt_version: str,
) -> ChatLlmStreamChunk:
    content = _message_content(response)
    usage = _message_usage(response)
    return ChatLlmStreamChunk(
        content=content,
        has_upstream_activity=_has_upstream_activity(response, content),
        model=model,
        prompt_version=prompt_version,
        input_tokens=usage[0],
        output_tokens=usage[1],
        total_tokens=usage[2],
    )


async def _close_stream(stream: AsyncIterator[Any] | None) -> None:
    if stream is None:
        return
    close = getattr(stream, "aclose", None)
    if close is None:
        return
    try:
        await close()
    except Exception:  # noqa: BLE001 - close errors must not hide the provider failure
        return


def _message_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "").strip()
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
    return str(content or "")


def _has_upstream_activity(response: Any, content: str) -> bool:
    """识别 Provider 已返回的正文或内部 reasoning，不暴露 reasoning 本文。"""

    if content.strip():
        return True
    response_metadata = getattr(response, "response_metadata", None)
    additional_kwargs = getattr(response, "additional_kwargs", None)
    return any(
        _has_nonempty_reasoning(value)
        for value in (
            getattr(response, "reasoning_content", None),
            _mapping_value(additional_kwargs, "reasoning_content"),
            _mapping_value(response_metadata, "reasoning_content"),
        )
    )


def _mapping_value(value: object, key: str) -> object:
    if isinstance(value, Mapping):
        return value.get(key)
    return None


def _has_nonempty_reasoning(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_nonempty_reasoning(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_nonempty_reasoning(item) for item in value)
    return False


def _request_messages(request: ChatLlmRequest) -> list[SystemMessage | HumanMessage | AIMessage]:
    messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=request.system_prompt)
    ]
    messages.extend(_history_message_to_langchain(message) for message in request.history_messages)
    messages.append(HumanMessage(content=request.user_prompt))
    return messages


def _history_message_to_langchain(
    message: ChatLlmMessage,
) -> SystemMessage | HumanMessage | AIMessage:
    if message.role is ChatLlmMessageRole.SYSTEM:
        return SystemMessage(content=message.content)
    if message.role is ChatLlmMessageRole.USER:
        return HumanMessage(content=message.content)
    return AIMessage(content=message.content)


def _message_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    usage = usage_metadata or response_metadata.get("token_usage") or {}

    input_tokens = _optional_int(usage.get("input_tokens", usage.get("prompt_tokens")))
    output_tokens = _optional_int(usage.get("output_tokens", usage.get("completion_tokens")))
    total_tokens = _optional_int(usage.get("total_tokens"))
    return input_tokens, output_tokens, total_tokens


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
