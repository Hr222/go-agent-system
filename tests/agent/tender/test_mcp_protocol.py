from __future__ import annotations

import asyncio
import base64

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.interfaces.agent.tender_mcp import TENDER_MCP_TOOL_NAME
from tests.agent.tender.test_mcp_adapter import _server


async def _protocol_call(tmp_path, arguments: dict[str, object]):  # noqa: ANN001
    server, provider, dispatcher, _ = _server(tmp_path)
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
    return result, provider, dispatcher


def test_streamable_http_protocol_lists_and_calls_v1_tool(tmp_path) -> None:  # noqa: ANN001
    result, _, dispatcher = asyncio.run(
        _protocol_call(
            tmp_path,
            {
                "file_name": "source.docx",
                "content_base64": base64.b64encode(b"source").decode("ascii"),
            },
        )
    )

    assert result.isError is False
    assert result.structuredContent["artifacts"][0]["file_name"] == "skeleton.docx"
    assert len(dispatcher.calls) == 1
    assert any(item.type == "resource" for item in result.content)


def test_streamable_http_protocol_returns_tool_error_for_invalid_arguments(tmp_path) -> None:  # noqa: ANN001
    result, provider, dispatcher = asyncio.run(_protocol_call(tmp_path, {}))

    assert result.isError is True
    assert "file_name" in result.content[0].text
    assert "content_base64" in result.content[0].text
    assert provider.calls == 0
    assert dispatcher.calls == []
