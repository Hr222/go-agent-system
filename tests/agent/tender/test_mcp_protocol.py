from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.interfaces.agent.tender_mcp import (
    TENDER_MCP_TOOL_NAME,
    create_tender_mcp_server,
)
from app.modules.agent.tender.contracts import (
    GeneratedTenderArtifact,
    TenderAnalysis,
    TenderGenerateSkeletonResult,
)


@dataclass
class FakeTenderApplication:
    result: TenderGenerateSkeletonResult
    calls: int = 0

    def execute(self, command: object) -> TenderGenerateSkeletonResult:
        self.calls += 1
        return self.result


def _result() -> TenderGenerateSkeletonResult:
    return TenderGenerateSkeletonResult(
        analysis=TenderAnalysis(
            status="completed",
            package_type="single_volume",
            summary="protocol smoke",
            outputs=[],
        ),
        artifacts=(
            GeneratedTenderArtifact(
                file_name="skeleton.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                content=b"docx-content",
            ),
        ),
        model="fake-model",
        prompt_version="tender-skeleton-v1",
    )


async def _protocol_call(arguments: dict[str, object]):
    fake_application = FakeTenderApplication(_result())
    server = create_tender_mcp_server(fake_application)
    mcp_app = server.streamable_http_app()
    transport = httpx.ASGITransport(app=mcp_app)

    async with server.session_manager.run():
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://localhost:8000",
        ) as http_client:
            async with streamable_http_client(
                "http://localhost:8000/mcp",
                http_client=http_client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(TENDER_MCP_TOOL_NAME, arguments)
    return result, fake_application


def test_streamable_http_protocol_lists_and_calls_v1_tool() -> None:
    result, fake_application = asyncio.run(
        _protocol_call(
            {
                "file_name": "source.docx",
                "content_base64": base64.b64encode(b"source").decode("ascii"),
            }
        )
    )

    assert result.isError is False
    assert result.structuredContent["artifacts"][0]["file_name"] == "skeleton.docx"
    assert fake_application.calls == 1
    assert any(item.type == "resource" for item in result.content)


def test_streamable_http_protocol_returns_tool_error_for_invalid_arguments() -> None:
    result, fake_application = asyncio.run(_protocol_call({}))

    assert result.isError is True
    assert "file_name" in result.content[0].text
    assert "content_base64" in result.content[0].text
    assert fake_application.calls == 0
