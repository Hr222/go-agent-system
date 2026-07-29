from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import ApplicationContainer
from app.interfaces.http.dependencies import get_stateless_application_container
from app.main import create_app
from app.modules.llm.contracts import ChatLlmRequest, ChatLlmStreamChunk
from app.shared.config import settings
from app.shared.exceptions import UpstreamServiceError


class FakeStreamingChatLlm:
    def __init__(
        self,
        chunks: list[ChatLlmStreamChunk],
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.requests: list[ChatLlmRequest] = []

    def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]:
        self.requests.append(request)

        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            for chunk in self.chunks:
                yield chunk
            if self.error is not None:
                raise self.error

        return generate()


def _application_for(llm: FakeStreamingChatLlm):
    application = create_app()
    container = ApplicationContainer(streaming_chat_llm=llm)
    application.dependency_overrides[get_stateless_application_container] = lambda: container
    return application


def test_llm_chat_stream_emits_ordered_sse_events_and_headers() -> None:
    application = _application_for(
        FakeStreamingChatLlm(
            [
                ChatLlmStreamChunk(content="你", model="glm-test", prompt_version="llm-chat-v1"),
                ChatLlmStreamChunk(
                    content="好", model="glm-test", prompt_version="llm-chat-v1", total_tokens=6
                ),
            ]
        )
    )

    with TestClient(application) as client:
        response = client.post("/api/v1/llm/chat/stream", json={"message": "  你好  "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    body = response.text
    assert body.index("event: meta") < body.index('"content":"你"') < body.index('"content":"好"')
    assert body.index('"content":"好"') < body.index("event: complete")


def test_llm_chat_stream_maps_pre_start_failure_to_http_error() -> None:
    application = _application_for(
        FakeStreamingChatLlm([], error=UpstreamServiceError("provider unavailable"))
    )

    with TestClient(application) as client:
        response = client.post("/api/v1/llm/chat/stream", json={"message": "你好"})

    assert response.status_code == 502
    assert response.json()["detail"] == "上游模型暂时不可用。"


def test_llm_chat_stream_emits_error_after_partial_response() -> None:
    application = _application_for(
        FakeStreamingChatLlm(
            [ChatLlmStreamChunk(content="部分内容", model="glm-test")],
            error=UpstreamServiceError("provider unavailable"),
        )
    )

    with TestClient(application) as client:
        response = client.post("/api/v1/llm/chat/stream", json={"message": "你好"})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "event: complete" not in response.text


def test_llm_chat_stream_rejects_when_concurrency_capacity_is_exhausted() -> None:
    llm = FakeStreamingChatLlm([ChatLlmStreamChunk(content="你好", model="glm-test")])
    application = _application_for(llm)

    with TestClient(application) as client:
        client.app.state.llm_stream_slots = asyncio.Semaphore(0)
        response = client.post("/api/v1/llm/chat/stream", json={"message": "你好"})

    assert response.status_code == 429
    assert llm.requests == []


def test_llm_chat_stream_maps_first_token_timeout_to_504(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DelayedStreamingChatLlm(FakeStreamingChatLlm):
        def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]:
            self.requests.append(request)

            async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
                await asyncio.sleep(0.05)
                yield ChatLlmStreamChunk(content="too late", model="glm-test")

            return generate()

    monkeypatch.setattr(settings, "llm_stream_first_token_timeout_seconds", 0.01)
    application = _application_for(DelayedStreamingChatLlm([]))

    with TestClient(application) as client:
        response = client.post("/api/v1/llm/chat/stream", json={"message": "你好"})

    assert response.status_code == 504


def test_nginx_streaming_proxy_config_disables_buffering() -> None:
    configuration = (
        Path(__file__).resolve().parents[2] / "docker" / "nginx" / "llm-streaming.conf"
    ).read_text(encoding="utf-8")

    assert "proxy_buffering off;" in configuration
    assert "proxy_http_version 1.1;" in configuration
    assert "proxy_read_timeout 130s;" in configuration
