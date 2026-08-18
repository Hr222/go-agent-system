from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_interaction_chat_stream_application
from app.main import create_app
from app.modules.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
    InteractionStreamEvent,
    InteractionStreamPreparation,
)
from app.modules.interaction.application.gateway import (
    DirectCapabilityExecution,
    GatewayResult,
)
from app.modules.interaction.domain.confirmation import ConfirmationProposal
from app.modules.llm.contracts import ChatLlmStreamChunk
from app.modules.security.domain.principal import RequestPrincipal


class RecordingGateway:
    def __init__(self, result: GatewayResult) -> None:
        self.result = result
        self.commands = []

    def recognize(self, command):  # noqa: ANN001
        self.commands.append(command)
        return self.result


class FakeStreamingChat:
    def __init__(
        self,
        chunks: list[ChatLlmStreamChunk],
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks
        self.error = error
        self.commands = []

    async def execute(self, command):  # noqa: ANN001
        self.commands.append(command)

        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            for chunk in self.chunks:
                yield chunk
            if self.error is not None:
                raise self.error

        return generate()


def _command() -> InteractionChatStreamCommand:
    return InteractionChatStreamCommand(
        user_input="解释一下向量检索",
        principal=RequestPrincipal.anonymous(),
        provided_inputs={},
    )


async def _connected() -> bool:
    return False


def test_chat_stream_emits_ordered_chat_events_after_server_authorization() -> None:
    gateway = RecordingGateway(
        GatewayResult(
            status="authorized",
            message="server authorized",
            direct_execution=DirectCapabilityExecution(
                capability_code="chat.general",
                dispatch_key="llm.chat",
                inputs={"message": "解释一下向量检索"},
            ),
        )
    )
    chat = FakeStreamingChat(
        [
            ChatLlmStreamChunk(content="向量检索", model="glm-test"),
            ChatLlmStreamChunk(content="用于语义召回。", total_tokens=8),
        ]
    )
    application = InteractionChatStreamApplication(gateway, chat)  # type: ignore[arg-type]

    async def scenario() -> list[object]:
        preparation = application.prepare(_command())
        assert preparation.kind == "chat"
        return [
            event
            async for event in application.stream(
                preparation,
                is_disconnected=_connected,
            )
        ]

    events = asyncio.run(scenario())

    assert [event.name for event in events] == ["meta", "delta", "delta", "complete"]
    assert [event.data.get("content") for event in events if event.name == "delta"] == [
        "向量检索",
        "用于语义召回。",
    ]
    assert events[-1].data["usage"] == {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": 8,
    }
    assert chat.commands[0].message == "解释一下向量检索"


def test_chat_stream_emits_approval_without_starting_model_execution() -> None:
    proposal = ConfirmationProposal(
        proposal_id="proposal-1",
        capability_code="tender.generate_bid_skeleton",
        dispatch_key="agent.tender.generate_bid_skeleton",
        inputs={"content_base64": "secret"},
        summary="生成投标骨架",
        confirmation_prompt="批准后才会执行。",
    )
    gateway = RecordingGateway(
        GatewayResult(status="pending", message="awaiting approval", proposal=proposal)
    )
    chat = FakeStreamingChat([])
    application = InteractionChatStreamApplication(gateway, chat)  # type: ignore[arg-type]

    async def scenario() -> list[object]:
        preparation = application.prepare(_command())
        return [
            event
            async for event in application.stream(
                preparation,
                is_disconnected=_connected,
            )
        ]

    events = asyncio.run(scenario())

    assert [event.name for event in events] == ["approval_required"]
    assert events[0].data == {
        "proposal_id": "proposal-1",
        "state": "pending",
        "summary": "生成投标骨架",
        "confirmation_prompt": "批准后才会执行。",
    }
    assert "dispatch_key" not in events[0].data
    assert "inputs" not in events[0].data
    assert chat.commands == []


def test_chat_stream_does_not_emit_complete_after_partial_model_failure() -> None:
    gateway = RecordingGateway(
        GatewayResult(
            status="authorized",
            message="server authorized",
            direct_execution=DirectCapabilityExecution(
                capability_code="chat.general",
                dispatch_key="llm.chat",
                inputs={"message": "你好"},
            ),
        )
    )
    chat = FakeStreamingChat(
        [ChatLlmStreamChunk(content="部分内容", model="glm-test")],
        error=RuntimeError("provider internal error"),
    )
    application = InteractionChatStreamApplication(gateway, chat)  # type: ignore[arg-type]

    async def scenario() -> list[object]:
        preparation = application.prepare(_command())
        return [
            event
            async for event in application.stream(
                preparation,
                is_disconnected=_connected,
            )
        ]

    events = asyncio.run(scenario())

    assert [event.name for event in events] == ["meta", "delta", "error"]
    assert events[-1].data["code"] == "UPSTREAM_STREAM_ERROR"
    assert "provider" not in str(events[-1].data)


def test_chat_stream_cancellation_closes_the_model_stream_without_complete() -> None:
    gateway = RecordingGateway(
        GatewayResult(
            status="authorized",
            message="server authorized",
            direct_execution=DirectCapabilityExecution(
                capability_code="chat.general",
                dispatch_key="llm.chat",
                inputs={"message": "你好"},
            ),
        )
    )

    class ClosableStreamingChat(FakeStreamingChat):
        closed = False

        async def execute(self, command):  # noqa: ANN001
            self.commands.append(command)

            async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
                try:
                    yield ChatLlmStreamChunk(content="部分内容", model="glm-test")
                    yield ChatLlmStreamChunk(content="不会继续显示")
                finally:
                    self.closed = True

            return generate()

    chat = ClosableStreamingChat([])
    application = InteractionChatStreamApplication(gateway, chat)  # type: ignore[arg-type]
    checks = 0

    async def disconnected_after_meta() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 1

    async def scenario() -> list[object]:
        preparation = application.prepare(_command())
        return [
            event
            async for event in application.stream(
                preparation,
                is_disconnected=disconnected_after_meta,
            )
        ]

    events = asyncio.run(scenario())

    assert [event.name for event in events] == ["meta"]
    assert chat.closed is True


def test_http_chat_stream_serializes_only_browser_safe_approval_data() -> None:
    class ApprovalOnlyApplication:
        def prepare(self, command):  # noqa: ANN001, ANN201
            del command
            return InteractionStreamPreparation(
                kind="single_event",
                event=InteractionStreamEvent(
                    "approval_required",
                    {
                        "proposal_id": "proposal-1",
                        "state": "pending",
                        "summary": "生成投标骨架",
                        "confirmation_prompt": "批准后才会执行。",
                    },
                ),
            )

        async def stream(self, preparation, *, is_disconnected):  # noqa: ANN001, ANN201
            del is_disconnected
            if preparation.event is not None:
                yield preparation.event

    application = create_app()
    application.dependency_overrides[get_interaction_chat_stream_application] = (
        ApprovalOnlyApplication
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/interaction/chat/stream",
            json={"user_input": "生成投标文件", "provided_inputs": {}},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: approval_required" in response.text
    assert '"proposal_id":"proposal-1"' in response.text
    assert "dispatch_key" not in response.text
    assert "content_base64" not in response.text
    application.dependency_overrides.clear()
