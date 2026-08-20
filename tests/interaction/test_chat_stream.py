from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import (
    get_intent_interaction_gateway,
    get_interaction_chat_stream_application,
)
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


def test_chat_stream_passes_conversation_context_to_gateway() -> None:
    gateway = RecordingGateway(
        GatewayResult(
            status="needs_clarification",
            message="需要更多信息。",
        )
    )
    application = InteractionChatStreamApplication(
        gateway,  # type: ignore[arg-type]
        FakeStreamingChat([]),  # type: ignore[arg-type]
    )
    conversation_id = UUID("00000000-0000-0000-0000-000000000001")

    preparation = application.prepare(
        InteractionChatStreamCommand(
            user_input="处理附件",
            principal=RequestPrincipal.anonymous(),
            provided_inputs={"source_document": "a" * 32},
            conversation_id=conversation_id,
        )
    )

    assert preparation.kind == "single_event"
    assert gateway.commands[0].conversation_id == conversation_id


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
            json={"user_input": "生成投标文件"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: approval_required" in response.text
    assert '"proposal_id":"proposal-1"' in response.text
    assert "dispatch_key" not in response.text
    assert "content_base64" not in response.text
    application.dependency_overrides.clear()


def test_http_chat_stream_accepts_user_context_but_rejects_capability_authority() -> None:
    class CapturingApplication:
        command: InteractionChatStreamCommand | None = None

        def prepare(self, command: InteractionChatStreamCommand):
            self.command = command
            return InteractionStreamPreparation(
                kind="single_event",
                event=InteractionStreamEvent("result", {"status": "unrecognized", "message": "无"}),
            )

        async def stream(self, preparation, *, is_disconnected):  # noqa: ANN001
            del is_disconnected
            if preparation.event is not None:
                yield preparation.event

    capturing = CapturingApplication()
    application = create_app()
    application.dependency_overrides[get_interaction_chat_stream_application] = lambda: capturing
    try:
        client = TestClient(application)
        accepted = client.post(
            "/api/v1/interaction/chat/stream",
            json={
                "user_input": "根据上传的招标文件生成骨架",
                "provided_inputs": {"file_name": "招标文件.docx"},
            },
        )
        rejected = client.post(
            "/api/v1/interaction/chat/stream",
            json={
                "user_input": "生成投标文件",
                "capability_code": "agent.tender.generate_bid_skeleton",
            },
        )
    finally:
        application.dependency_overrides.clear()

    assert accepted.status_code == 200
    assert capturing.command is not None
    assert capturing.command.provided_inputs == {"file_name": "招标文件.docx"}
    assert rejected.status_code == 422


def test_removed_direct_dialogue_agent_endpoint_is_not_registered() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/dialogue/agent-invocations",
            json={
                "capability_code": "agent.tender.generate_bid_skeleton",
                "inputs": {"file_name": "不应执行.docx"},
            },
        )

    assert response.status_code == 404


def test_http_confirmation_uses_dialogue_agent_result_when_context_is_bound() -> None:
    class DialogueConfirmationApplication:
        def __init__(self) -> None:
            self.commands = []

        def confirm_agent(self, command):  # noqa: ANN001
            self.commands.append(command)
            return GatewayResult(
                status="completed",
                message="Agent 已完成执行。",
                execution_result={
                    "answer": "投标骨架已经生成。",
                    "agent_result": {
                        "artifact": {"file_name": "骨架.docx", "size": 42}
                    },
                },
            )

    class UnexpectedGateway:
        def confirm(self, command):  # noqa: ANN001
            raise AssertionError("已绑定的对话 Agent 不应进入通用分发确认路径")

    dialogue_application = DialogueConfirmationApplication()
    application = create_app()
    application.dependency_overrides[get_interaction_chat_stream_application] = (
        lambda: dialogue_application
    )
    application.dependency_overrides[get_intent_interaction_gateway] = UnexpectedGateway
    try:
        response = TestClient(application).post(
            "/api/v1/interaction/proposals/proposal-agent-1/confirmation",
            json={"action": "confirm"},
        )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["execution_result"] == {
        "answer": "投标骨架已经生成。",
        "agent_result": {"artifact": {"file_name": "骨架.docx", "size": 42}},
    }
    assert dialogue_application.commands[0].proposal_id == "proposal-agent-1"


def test_http_confirmation_keeps_agent_result_when_continuation_fails() -> None:
    class FailedContinuationApplication:
        def confirm_agent(self, command):  # noqa: ANN001
            del command
            return GatewayResult(
                status="failed",
                message="Agent 已完成，但最终回复暂时无法生成。",
                execution_result={
                    "agent_result": {
                        "artifact": {"file_name": "骨架.docx", "size": 42}
                    }
                },
                error_code="CONTINUATION_LLM_UNAVAILABLE",
            )

    application = create_app()
    application.dependency_overrides[get_interaction_chat_stream_application] = (
        FailedContinuationApplication
    )
    try:
        response = TestClient(application).post(
            "/api/v1/interaction/proposals/proposal-agent-1/confirmation",
            json={"action": "confirm"},
        )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "CONTINUATION_LLM_UNAVAILABLE"
    assert body["execution_result"]["agent_result"]["artifact"]["file_name"] == "骨架.docx"
