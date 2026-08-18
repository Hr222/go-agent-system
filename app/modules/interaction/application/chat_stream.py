from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Literal
from uuid import uuid4

from app.modules.interaction.application.gateway import (
    DirectCapabilityExecution,
    GatewayRecognitionCommand,
    GatewayResult,
    IntentInteractionGateway,
)
from app.modules.llm.application.chat import ChatCommand
from app.modules.llm.application.streaming_chat import StreamingChatApplication
from app.modules.llm.contracts import ChatLlmStreamChunk
from app.modules.security.domain.principal import RequestPrincipal
from app.shared.config import settings

InteractionStreamEventName = Literal[
    "meta",
    "delta",
    "complete",
    "approval_required",
    "result",
    "error",
    "heartbeat",
]
DisconnectChecker = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class InteractionChatStreamCommand:
    user_input: str
    principal: RequestPrincipal
    provided_inputs: dict[str, object]


@dataclass(frozen=True, slots=True)
class InteractionStreamEvent:
    name: InteractionStreamEventName
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class InteractionStreamPreparation:
    """A safe routing result prepared before an SSE response starts."""

    kind: Literal["chat", "single_event"]
    event: InteractionStreamEvent | None = None
    direct_execution: DirectCapabilityExecution | None = None


class InteractionChatStreamApplication:
    """Route a chat request on the server, then emit controlled interaction events."""

    def __init__(
        self,
        gateway: IntentInteractionGateway,
        streaming_chat: StreamingChatApplication,
    ) -> None:
        self._gateway = gateway
        self._streaming_chat = streaming_chat

    def prepare(
        self,
        command: InteractionChatStreamCommand,
    ) -> InteractionStreamPreparation:
        """Complete routing before model execution or an SSE response begins."""

        try:
            result = self._gateway.recognize(
                GatewayRecognitionCommand(
                    user_input=command.user_input,
                    principal=command.principal,
                    provided_inputs=dict(command.provided_inputs),
                )
            )
        except Exception:  # noqa: BLE001 - never expose interaction internals
            return _single_error("INTERACTION_UNAVAILABLE", "请求暂时无法处理。")

        if result.status != "authorized":
            return InteractionStreamPreparation(
                kind="single_event",
                event=_result_event(result),
            )

        direct_execution = result.direct_execution
        if not _is_general_chat_execution(direct_execution):
            return _single_error(
                "UNSUPPORTED_UNCONFIRMED_CAPABILITY",
                "该请求暂时无法通过当前对话通道处理。",
            )
        return InteractionStreamPreparation(
            kind="chat",
            direct_execution=direct_execution,
        )

    async def stream(
        self,
        preparation: InteractionStreamPreparation,
        *,
        is_disconnected: DisconnectChecker,
    ) -> AsyncIterator[InteractionStreamEvent]:
        """Emit the selected controlled response without leaking LLM internals."""

        if preparation.kind == "single_event":
            if preparation.event is not None:
                yield preparation.event
            return

        direct_execution = preparation.direct_execution
        if not _is_general_chat_execution(direct_execution):
            yield _error_event(
                "UNSUPPORTED_UNCONFIRMED_CAPABILITY",
                "该请求暂时无法通过当前对话通道处理。",
                retryable=False,
            )
            return

        message = direct_execution.inputs["message"]
        assert isinstance(message, str)
        stream: AsyncIterator[ChatLlmStreamChunk] | None = None
        try:
            stream = await self._streaming_chat.execute(ChatCommand(message=message))
            first_chunk = await asyncio.wait_for(
                _prime_stream(stream),
                timeout=settings.llm_stream_first_token_timeout_seconds,
            )
        except asyncio.TimeoutError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("UPSTREAM_TIMEOUT", "上游模型响应超时。")
            return
        except ValueError:
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("CHAT_INPUT_INVALID", "请求内容无效。", retryable=False)
            return
        except Exception:  # noqa: BLE001 - never expose provider internals
            if stream is not None:
                await _close_stream(stream)
            yield _error_event("UPSTREAM_UNAVAILABLE", "上游模型暂时不可用。")
            return

        request_id = str(uuid4())
        model = first_chunk.model or "unknown"
        prompt_version = first_chunk.prompt_version or "llm-chat-v1"
        latest = first_chunk
        try:
            yield InteractionStreamEvent(
                "meta",
                {
                    "request_id": request_id,
                    "model": model,
                    "prompt_version": prompt_version,
                },
            )
            async for chunk in _stream_with_heartbeats(
                stream,
                first_chunk,
                is_disconnected=is_disconnected,
            ):
                if await is_disconnected():
                    return
                if chunk is None:
                    yield InteractionStreamEvent("heartbeat", {"request_id": request_id})
                    continue
                latest = chunk
                if chunk.content:
                    yield InteractionStreamEvent(
                        "delta",
                        {"request_id": request_id, "content": chunk.content},
                    )
            if await is_disconnected():
                return
            yield InteractionStreamEvent(
                "complete",
                {
                    "request_id": request_id,
                    "model": latest.model or model,
                    "prompt_version": latest.prompt_version or prompt_version,
                    "usage": {
                        "input_tokens": latest.input_tokens,
                        "output_tokens": latest.output_tokens,
                        "total_tokens": latest.total_tokens,
                    },
                },
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            yield _error_event("UPSTREAM_TIMEOUT", "上游模型响应超时。")
        except Exception:  # noqa: BLE001 - never expose provider internals
            yield _error_event("UPSTREAM_STREAM_ERROR", "模型生成过程中发生错误。")
        finally:
            await _close_stream(stream)


def _is_general_chat_execution(
    execution: DirectCapabilityExecution | None,
) -> bool:
    if execution is None:
        return False
    return (
        execution.capability_code == "chat.general"
        and execution.dispatch_key == "llm.chat"
        and isinstance(execution.inputs.get("message"), str)
        and bool(execution.inputs["message"].strip())
    )


def _single_error(code: str, message: str) -> InteractionStreamPreparation:
    return InteractionStreamPreparation(
        kind="single_event",
        event=_error_event(code, message, retryable=False),
    )


def _result_event(result: GatewayResult) -> InteractionStreamEvent:
    if result.status == "pending" and result.proposal is not None:
        return InteractionStreamEvent(
            "approval_required",
            {
                "proposal_id": result.proposal.proposal_id,
                "state": result.proposal.state,
                "summary": result.proposal.summary,
                "confirmation_prompt": result.proposal.confirmation_prompt,
            },
        )
    return InteractionStreamEvent(
        "result",
        {
            "status": result.status,
            "message": result.message,
            "error_code": result.error_code,
        },
    )


def _error_event(
    code: str,
    message: str,
    *,
    retryable: bool = True,
) -> InteractionStreamEvent:
    return InteractionStreamEvent(
        "error",
        {"code": code, "message": message, "retryable": retryable},
    )


async def _prime_stream(
    stream: AsyncIterator[ChatLlmStreamChunk],
) -> ChatLlmStreamChunk:
    try:
        async for chunk in stream:
            if chunk.content.strip():
                return chunk
    except Exception:
        await _close_stream(stream)
        raise

    await _close_stream(stream)
    raise RuntimeError("LLM returned an empty response.")


async def _stream_with_heartbeats(
    stream: AsyncIterator[ChatLlmStreamChunk],
    first_chunk: ChatLlmStreamChunk,
    *,
    is_disconnected: DisconnectChecker,
) -> AsyncIterator[ChatLlmStreamChunk | None]:
    yield first_chunk
    deadline = monotonic() + settings.llm_stream_total_timeout_seconds
    last_chunk_at = monotonic()
    next_chunk = asyncio.create_task(anext(stream))
    try:
        while True:
            now = monotonic()
            remaining = min(
                deadline - now,
                settings.llm_stream_idle_timeout_seconds - (now - last_chunk_at),
                settings.llm_stream_heartbeat_seconds,
            )
            if remaining <= 0:
                raise asyncio.TimeoutError
            done, _ = await asyncio.wait({next_chunk}, timeout=remaining)
            if not done:
                if await is_disconnected():
                    return
                yield None
                continue
            try:
                chunk = next_chunk.result()
            except StopAsyncIteration:
                return
            last_chunk_at = monotonic()
            yield chunk
            next_chunk = asyncio.create_task(anext(stream))
    finally:
        if not next_chunk.done():
            next_chunk.cancel()
            await asyncio.gather(next_chunk, return_exceptions=True)


async def _close_stream(stream: AsyncIterator[ChatLlmStreamChunk]) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None:
        await close()
