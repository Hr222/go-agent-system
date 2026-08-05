from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextContent,
)

from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import (
    TenderExtractFormatSectionCommand,
    TenderGenerateSkeletonCommand,
    TenderVerifyExtractionBoundaryCommand,
)
from app.modules.agent.tender.errors import (
    TenderAnalysisError,
    TenderDocumentParseError,
    TenderInputError,
    TenderRenderError,
)
from app.shared.config import settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError

TENDER_MCP_SERVER_NAME = "tender-agent"
TENDER_MCP_TOOL_NAME = "tender.generate_bid_skeleton"
TENDER_MCP_EXTRACT_TOOL_NAME = "tender.extract_bid_format_section"
TENDER_MCP_VERIFY_TOOL_NAME = "tender.verify_extraction_boundary"
TENDER_MCP_MOUNT_PATH = "/api/v1/mcp/tender"


TenderApplicationProvider = Callable[[], TenderApplication]


def create_tender_mcp_server(
    application: TenderApplication | TenderApplicationProvider,
) -> FastMCP:
    """创建只负责协议适配的 Tender MCP Server。"""

    server = FastMCP(
        TENDER_MCP_SERVER_NAME,
        instructions="提供招标文件分析和投标骨架生成能力。",
        stateless_http=True,
        streamable_http_path="/mcp",
        max_request_body_size=(settings.tender_hard_max_size_bytes * 4 // 3) + 1024 * 1024,
    )

    @server.tool(
        name=TENDER_MCP_TOOL_NAME,
        description="读取当前 DOCX 招标文件并生成一个或多个可填写的投标骨架文件。",
        structured_output=False,
    )
    def generate_bid_skeleton(
        file_name: str,
        content_base64: str,
        user_focus: str | None = None,
    ) -> CallToolResult:
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            return _error_result("INVALID_INPUT", "文件内容不是有效的 Base64。", exc)

        try:
            resolved_application = (
                application() if callable(application) else application
            )
            result = resolved_application.execute(
                TenderGenerateSkeletonCommand(
                    file_name=file_name,
                    content=content,
                    user_focus=user_focus,
                )
            )
        except Exception as exc:  # noqa: BLE001 - 统一转换为 MCP 工具错误
            return _error_result(*_map_error(exc))

        metadata = [
            {
                "file_name": artifact.file_name,
                "media_type": artifact.media_type,
                "size_bytes": len(artifact.content),
                "resource_uri": _artifact_uri(artifact.file_name),
            }
            for artifact in result.artifacts
        ]
        content_blocks: list[Any] = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "analysis": result.analysis.model_dump(mode="json"),
                        "artifacts": metadata,
                        "model": result.model,
                        "prompt_version": result.prompt_version,
                    },
                    ensure_ascii=False,
                ),
            )
        ]
        for artifact in result.artifacts:
            content_blocks.append(
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri=_artifact_uri(artifact.file_name),
                        mimeType=artifact.media_type,
                        blob=base64.b64encode(artifact.content).decode("ascii"),
                    ),
                )
            )
        return CallToolResult(
            content=content_blocks,
            structuredContent={
                "analysis": result.analysis.model_dump(mode="json"),
                "artifacts": metadata,
                "model": result.model,
                "prompt_version": result.prompt_version,
            },
        )

    @server.tool(
        name=TENDER_MCP_EXTRACT_TOOL_NAME,
        description="Copy a confirmed bid-format range from the source DOCX.",
        structured_output=False,
    )
    def extract_bid_format_section(
        file_name: str,
        content_base64: str,
        start_block_id: str,
        end_block_id: str,
        output_name: str | None = None,
    ) -> CallToolResult:
        try:
            content = _decode_base64(content_base64)
        except (binascii.Error, ValueError) as exc:
            return _error_result("INVALID_INPUT", "File content is not valid Base64.", exc)

        try:
            resolved_application = application() if callable(application) else application
            result = resolved_application.extract_bid_format_section(
                TenderExtractFormatSectionCommand(
                    file_name=file_name,
                    content=content,
                    start_block_id=start_block_id,
                    end_block_id=end_block_id,
                    output_name=output_name,
                )
            )
        except Exception as exc:  # noqa: BLE001 - stable MCP tool error boundary
            return _error_result(*_map_error(exc))

        artifact = result.artifact
        metadata = {
            "file_name": artifact.file_name,
            "media_type": artifact.media_type,
            "size_bytes": len(artifact.content),
            "resource_uri": _artifact_uri(artifact.file_name),
        }
        structured = {
            "start_block_id": result.start_block_id,
            "end_block_id": result.end_block_id,
            "block_count": result.block_count,
            "table_count": result.table_count,
            "artifact": metadata,
        }
        return _artifact_result(
            artifact.content,
            artifact.media_type,
            artifact.file_name,
            structured,
        )

    @server.tool(
        name=TENDER_MCP_VERIFY_TOOL_NAME,
        description=(
            "Return source context around candidate extraction boundaries for Agent review."
        ),
        structured_output=False,
    )
    def verify_extraction_boundary(
        file_name: str,
        content_base64: str,
        start_block_id: str,
        end_block_id: str,
        context_radius: int = 3,
    ) -> CallToolResult:
        try:
            content = _decode_base64(content_base64)
        except (binascii.Error, ValueError) as exc:
            return _error_result("INVALID_INPUT", "File content is not valid Base64.", exc)

        try:
            resolved_application = application() if callable(application) else application
            result = resolved_application.verify_extraction_boundary(
                TenderVerifyExtractionBoundaryCommand(
                    file_name=file_name,
                    content=content,
                    start_block_id=start_block_id,
                    end_block_id=end_block_id,
                    context_radius=context_radius,
                )
            )
        except Exception as exc:  # noqa: BLE001 - stable MCP tool error boundary
            return _error_result(*_map_error(exc))

        structured = {
            "start_block_id": result.start_block_id,
            "end_block_id": result.end_block_id,
            "start_position": result.start_position,
            "end_position": result.end_position,
            "context": [
                {
                    "block_id": block.block_id,
                    "kind": block.kind,
                    "text": block.text,
                    "order": block.order,
                    "position": block.position,
                    "heading_path": list(block.heading_path),
                }
                for block in result.context
            ],
        }
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False))],
            structuredContent=structured,
        )

    return server


def _decode_base64(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _artifact_result(
    content: bytes,
    media_type: str,
    file_name: str,
    structured: dict[str, Any],
) -> CallToolResult:
    resource_uri = _artifact_uri(file_name)
    content_blocks: list[Any] = [
        TextContent(type="text", text=json.dumps(structured, ensure_ascii=False)),
        EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=resource_uri,
                mimeType=media_type,
                blob=base64.b64encode(content).decode("ascii"),
            ),
        ),
    ]
    return CallToolResult(
        content=content_blocks,
        structuredContent=structured,
    )


def _artifact_uri(file_name: str) -> str:
    safe_name = PurePosixPath(file_name).name.replace(" ", "_")
    return f"tender://artifacts/{safe_name}"


def _map_error(exc: Exception) -> tuple[str, str, Exception]:
    if isinstance(exc, TenderInputError):
        return "INVALID_INPUT", str(exc), exc
    if isinstance(exc, TenderDocumentParseError):
        return "DOCUMENT_PARSE_FAILED", "招标 DOCX 解析失败。", exc
    if isinstance(exc, ServiceNotConfiguredError):
        return "SERVICE_NOT_CONFIGURED", "Tender Agent 的模型服务尚未完成配置。", exc
    if isinstance(exc, UpstreamServiceError):
        return "UPSTREAM_FAILED", "Tender Agent 的模型服务调用失败。", exc
    if isinstance(exc, TenderAnalysisError):
        return "ANALYSIS_FAILED", "招标文件结构化分析结果无效。", exc
    if isinstance(exc, TenderRenderError):
        return "RENDER_FAILED", "投标骨架文件生成失败。", exc
    return "INTERNAL_ERROR", "Tender Agent 处理失败。", exc


def _error_result(code: str, message: str, cause: Exception) -> CallToolResult:
    del cause
    return CallToolResult(
        content=[TextContent(type="text", text=f"{code}: {message}")],
        structuredContent={"error_code": code, "message": message},
        isError=True,
    )
