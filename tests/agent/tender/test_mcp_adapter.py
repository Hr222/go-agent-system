from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from mcp.types import CallToolResult, EmbeddedResource

from app.infrastructure.filesystem.attachment_storage import FilesystemAttachmentStorage
from app.interfaces.agent.tender_mcp import (
    TENDER_MCP_EXTRACT_TOOL_NAME,
    TENDER_MCP_TOOL_NAME,
    TENDER_MCP_VERIFY_TOOL_NAME,
    create_tender_mcp_server,
)
from app.platform.attachment import AttachmentAccessContext
from app.platform.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatchResult,
)
from app.platform.interaction.domain.agent_call import (
    AgentCallError,
    AgentCallResult,
    StructuredAgentCall,
)
from app.platform.interaction.domain.attachment import ResolvedAttachment
from app.platform.interaction.ports.mcp_dispatch import McpDispatchScope
from app.platform.security import AnonymousPrincipalResolver, StaticPrincipalResolver

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass
class RecordingDispatcher:
    storage: FilesystemAttachmentStorage
    calls: list[AgentCallDispatchCommand] = field(default_factory=list)
    error_code: str | None = None
    accepted: bool = False

    def dispatch(self, command: AgentCallDispatchCommand) -> AgentCallDispatchResult:
        self.calls.append(command)
        if self.accepted:
            return AgentCallDispatchResult(
                status="accepted",
                call=command.call,
                execution_reference="task:accepted-1",
            )
        if self.error_code is not None:
            return AgentCallDispatchResult(
                status="failed",
                call=command.call,
                error=AgentCallError(
                    **command.call.model_dump(mode="python", exclude={"inputs"}),
                    error_code=self.error_code,
                    message="private implementation detail",
                ),
            )

        output = self._output(command.call, command.principal.subject or "")
        return AgentCallDispatchResult(
            status="completed",
            call=command.call,
            result=AgentCallResult(
                **command.call.model_dump(mode="python", exclude={"inputs"}),
                output=output,
            ),
        )

    def _output(self, call: StructuredAgentCall, subject: str) -> dict[str, object]:
        source = call.inputs["source_document"]
        assert isinstance(source, ResolvedAttachment)
        assert source.content == b"source"
        assert "content_base64" not in call.inputs
        if call.capability_code == "tender.generate_bid_skeleton":
            return {
                "analysis": {"status": "completed", "summary": "test"},
                "artifacts": [self._artifact("skeleton.docx", subject)],
                "model": "fake-model",
                "prompt_version": "tender-skeleton-v1",
            }
        if call.capability_code == "tender.extract_bid_format_section":
            return {
                "start_block_id": call.inputs["start_block_id"],
                "end_block_id": call.inputs["end_block_id"],
                "block_count": 2,
                "table_count": 1,
                "artifact": self._artifact("format.docx", subject),
            }
        return {
            "start_block_id": call.inputs["start_block_id"],
            "end_block_id": call.inputs["end_block_id"],
            "start_position": 1,
            "end_position": 2,
            "context": [
                {
                    "block_id": call.inputs["start_block_id"],
                    "kind": "paragraph",
                    "text": "format start",
                    "order": 2,
                    "position": 1,
                    "heading_path": ["Bid format"],
                }
            ],
        }

    def _artifact(self, file_name: str, subject: str) -> dict[str, object]:
        reference = self.storage.stage_attachment(
            file_name=file_name,
            media_type=_DOCX_MEDIA_TYPE,
            file_stream=BytesIO(b"docx-content"),
            context=AttachmentAccessContext(subject=subject),
        )
        return {
            "file_name": reference.file_name,
            "media_type": reference.media_type,
            "size": reference.size_bytes,
            "resource_id": reference.attachment_id,
        }


@dataclass
class ScopeProvider:
    dispatcher: RecordingDispatcher
    storage: FilesystemAttachmentStorage
    calls: int = 0

    @contextmanager
    def __call__(self, principal):  # noqa: ANN001
        self.calls += 1
        yield McpDispatchScope(
            dispatcher=self.dispatcher,  # type: ignore[arg-type]
            attachment_storage=self.storage,
            principal=principal,
        )


def _server(
    tmp_path: Path,
    *,
    resolver=None,  # noqa: ANN001
    error_code: str | None = None,
    accepted: bool = False,
):  # noqa: ANN001
    storage = FilesystemAttachmentStorage(
        tmp_path,
        allowed_media_types=(_DOCX_MEDIA_TYPE,),
    )
    dispatcher = RecordingDispatcher(
        storage=storage,
        error_code=error_code,
        accepted=accepted,
    )
    provider = ScopeProvider(dispatcher=dispatcher, storage=storage)
    server = create_tender_mcp_server(
        provider,
        principal_resolver=resolver
        or StaticPrincipalResolver(
            subject="mcp-user",
            permissions=("agent:tender:execute",),
        ),
    )
    return server, provider, dispatcher, storage


def _source_arguments() -> dict[str, object]:
    return {
        "file_name": "source.docx",
        "content_base64": base64.b64encode(b"source").decode("ascii"),
    }


def test_tender_mcp_lists_only_v1_tools(tmp_path: Path) -> None:
    server, _, _, _ = _server(tmp_path)

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == [
        TENDER_MCP_TOOL_NAME,
        TENDER_MCP_EXTRACT_TOOL_NAME,
        TENDER_MCP_VERIFY_TOOL_NAME,
    ]
    assert "content_base64" in tools[0].inputSchema["properties"]
    assert "start_block_id" in tools[1].inputSchema["required"]
    assert "end_block_id" in tools[2].inputSchema["required"]
    assert "tender.fill_bid_content" not in [tool.name for tool in tools]


def test_tender_mcp_routes_skeleton_through_dispatcher_and_returns_resource(tmp_path: Path) -> None:
    server, _, dispatcher, storage = _server(tmp_path)

    response = asyncio.run(server.call_tool(TENDER_MCP_TOOL_NAME, _source_arguments()))

    assert isinstance(response, CallToolResult)
    assert response.isError is False
    assert response.structuredContent["artifacts"][0]["file_name"] == "skeleton.docx"
    assert "resource_id" not in response.structuredContent["artifacts"][0]
    assert any(isinstance(block, EmbeddedResource) for block in response.content)
    assert [call.call.capability_code for call in dispatcher.calls] == [
        "tender.generate_bid_skeleton"
    ]
    call = dispatcher.calls[0].call
    assert call.call_id and call.run_id
    assert call.conversation_id is None
    assert call.turn_id is None
    assert call.parent_run_id is None
    assert list(storage.attachment_root.iterdir()) == []


def test_tender_mcp_routes_format_extraction_through_dispatcher(tmp_path: Path) -> None:
    server, _, dispatcher, _ = _server(tmp_path)

    response = asyncio.run(
        server.call_tool(
            TENDER_MCP_EXTRACT_TOOL_NAME,
            {
                **_source_arguments(),
                "start_block_id": "evidence-2",
                "end_block_id": "evidence-4",
            },
        )
    )

    assert response.isError is False
    assert response.structuredContent["block_count"] == 2
    assert any(isinstance(block, EmbeddedResource) for block in response.content)
    assert dispatcher.calls[0].call.capability_code == "tender.extract_bid_format_section"


def test_tender_mcp_preserves_input_attachment_for_accepted_async_task(tmp_path: Path) -> None:
    server, _, _, storage = _server(tmp_path, accepted=True)

    response = asyncio.run(server.call_tool(TENDER_MCP_TOOL_NAME, _source_arguments()))

    assert response.isError is False
    assert response.structuredContent == {
        "status": "accepted",
        "execution_reference": "task:accepted-1",
    }
    assert len(list(storage.attachment_root.iterdir())) == 1


def test_tender_mcp_routes_boundary_verification_through_dispatcher(tmp_path: Path) -> None:
    server, _, dispatcher, _ = _server(tmp_path)

    response = asyncio.run(
        server.call_tool(
            TENDER_MCP_VERIFY_TOOL_NAME,
            {
                **_source_arguments(),
                "start_block_id": "evidence-2",
                "end_block_id": "evidence-4",
            },
        )
    )

    assert response.isError is False
    assert response.structuredContent["context"][0]["block_id"] == "evidence-2"
    assert dispatcher.calls[0].call.capability_code == "tender.verify_extraction_boundary"


def test_tender_mcp_rejects_anonymous_principal_before_scope_or_dispatch(tmp_path: Path) -> None:
    server, provider, dispatcher, _ = _server(
        tmp_path,
        resolver=AnonymousPrincipalResolver(),
    )

    response = asyncio.run(server.call_tool(TENDER_MCP_TOOL_NAME, _source_arguments()))

    assert response.isError is True
    assert response.structuredContent["error_code"] == "AUTHENTICATION_REQUIRED"
    assert provider.calls == 0
    assert dispatcher.calls == []


def test_tender_mcp_rejects_invalid_base64_before_scope_or_dispatch(tmp_path: Path) -> None:
    server, provider, dispatcher, _ = _server(tmp_path)

    response = asyncio.run(
        server.call_tool(
            TENDER_MCP_TOOL_NAME,
            {"file_name": "source.docx", "content_base64": "not-base64"},
        )
    )

    assert response.isError is True
    assert response.structuredContent["error_code"] == "INVALID_INPUT"
    assert provider.calls == 0
    assert dispatcher.calls == []


def test_tender_mcp_maps_dispatcher_errors_without_internal_details(tmp_path: Path) -> None:
    server, _, _, _ = _server(tmp_path, error_code="DOCUMENT_PARSE_FAILED")

    response = asyncio.run(server.call_tool(TENDER_MCP_TOOL_NAME, _source_arguments()))

    assert response.isError is True
    assert response.structuredContent == {
        "error_code": "DOCUMENT_PARSE_FAILED",
        "message": "招标 DOCX 解析失败。",
    }
    assert "private implementation detail" not in response.content[0].text


def test_tender_mcp_exposes_streamable_http_app(tmp_path: Path) -> None:
    server, _, _, _ = _server(tmp_path)

    assert server.streamable_http_app() is not None
