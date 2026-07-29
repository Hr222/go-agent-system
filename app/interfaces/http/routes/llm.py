from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.composition import ApplicationContainer
from app.interfaces.http.dependencies import (
    get_chat_application,
    get_stateless_application_container,
)
from app.interfaces.http.schemas.llm import LlmChatRequest, LlmChatResponse, LlmUsage
from app.interfaces.http.streaming import serialize_sse_event
from app.modules.llm.application.chat import ChatApplication, ChatCommand
from app.modules.llm.contracts import ChatLlmStreamChunk
from app.shared.config import settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError
from app.shared.logging import get_logger

router = APIRouter()
logger = get_logger("app.interfaces.http.llm")


@router.post("/chat", response_model=LlmChatResponse)
async def chat(
    request: LlmChatRequest,
    application: ChatApplication = Depends(get_chat_application),
) -> LlmChatResponse:
    """执行一次不保存上下文、不调用工具的 LLM 单轮请求。"""

    try:
        result = application.execute(ChatCommand(message=request.message))
    except ServiceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LlmChatResponse(
        answer=result.answer,
        model=result.model,
        prompt_version=result.prompt_version,
        usage=LlmUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
        ),
    )


@router.post("/chat/stream")
async def chat_stream(
    http_request: Request,
    request: LlmChatRequest,
    container: ApplicationContainer = Depends(get_stateless_application_container),
) -> StreamingResponse:
    """执行一次单轮 LLM 请求，并以 SSE 增量返回模型回答。"""

    request_id = str(uuid4())
    stream_slots: asyncio.Semaphore = http_request.app.state.llm_stream_slots
    if stream_slots.locked():
        raise HTTPException(status_code=429, detail="流式请求达到并发上限。")

    await stream_slots.acquire()
    started_at = monotonic()
    try:
        application = container.streaming_chat_application()
        stream = await application.execute(ChatCommand(message=request.message))
        first_chunk = await asyncio.wait_for(
            _prime_stream(stream),
            timeout=settings.llm_stream_first_token_timeout_seconds,
        )
    except ServiceNotConfiguredError as exc:
        stream_slots.release()
        raise HTTPException(status_code=503, detail="LLM 服务未配置。") from exc
    except UpstreamServiceError as exc:
        stream_slots.release()
        raise HTTPException(status_code=502, detail="上游模型暂时不可用。") from exc
    except asyncio.TimeoutError as exc:
        await _close_stream(stream)
        stream_slots.release()
        raise HTTPException(status_code=504, detail="上游模型响应超时。") from exc
    except ValueError as exc:
        stream_slots.release()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        stream_slots.release()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        stream_slots.release()
        raise HTTPException(status_code=502, detail="上游模型暂时不可用。") from exc

    async def events() -> AsyncIterator[str]:
        model = first_chunk.model or "unknown"
        prompt_version = first_chunk.prompt_version or "llm-chat-v1"
        latest = first_chunk
        phase = "completed"
        event_count = 0

        try:
            yield serialize_sse_event(
                "meta",
                {
                    "request_id": request_id,
                    "model": model,
                    "prompt_version": prompt_version,
                },
            )
            event_count += 1

            async for chunk in _stream_with_heartbeats(
                stream,
                first_chunk,
                http_request,
            ):
                if chunk is None:
                    yield serialize_sse_event("heartbeat", {"request_id": request_id})
                    event_count += 1
                    continue
                latest = chunk
                if chunk.content:
                    yield serialize_sse_event(
                        "delta",
                        {"request_id": request_id, "content": chunk.content},
                    )
                    event_count += 1
        except asyncio.CancelledError:
            phase = "cancelled"
            raise
        except asyncio.TimeoutError:
            phase = "timed_out"
            yield serialize_sse_event(
                "error",
                {
                    "request_id": request_id,
                    "code": "UPSTREAM_TIMEOUT",
                    "message": "上游模型响应超时。",
                    "retryable": True,
                },
            )
        except Exception:
            phase = "failed"
            yield serialize_sse_event(
                "error",
                {
                    "request_id": request_id,
                    "code": "UPSTREAM_STREAM_ERROR",
                    "message": "上游模型在生成过程中失败。",
                    "retryable": True,
                },
            )
        else:
            usage = {
                "input_tokens": latest.input_tokens,
                "output_tokens": latest.output_tokens,
                "total_tokens": latest.total_tokens,
            }
            yield serialize_sse_event(
                "complete",
                {
                    "request_id": request_id,
                    "model": latest.model or model,
                    "prompt_version": latest.prompt_version or prompt_version,
                    "usage": usage,
                },
            )
            event_count += 1
        finally:
            await _close_stream(stream)
            stream_slots.release()
            http_request.app.state.llm_active_streams = max(
                0, http_request.app.state.llm_active_streams - 1
            )
            logger.info(
                "llm_stream request_id=%s phase=%s duration_ms=%.2f events=%s active_streams=%s",
                request_id,
                phase,
                (monotonic() - started_at) * 1000,
                event_count,
                http_request.app.state.llm_active_streams,
            )

    http_request.app.state.llm_active_streams += 1
    logger.info(
        "llm_stream request_id=%s phase=connected active_streams=%s",
        request_id,
        http_request.app.state.llm_active_streams,
    )
    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _prime_stream(
    stream: AsyncIterator[ChatLlmStreamChunk],
) -> ChatLlmStreamChunk:
    """预取首个有效片段，让首片段前的 Provider 错误仍能映射为 HTTP 状态。"""

    try:
        async for chunk in stream:
            if chunk.content.strip():
                return chunk
    except Exception:
        await _close_stream(stream)
        raise

    await _close_stream(stream)
    raise RuntimeError("LLM 返回了空响应。")


async def _stream_with_heartbeats(
    stream: AsyncIterator[ChatLlmStreamChunk],
    first_chunk: ChatLlmStreamChunk,
    request: Request,
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
                if await request.is_disconnected():
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
