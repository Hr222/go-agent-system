from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent

from app.platform.attachment import AttachmentAccessContext, AttachmentStoragePort
from app.platform.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatchResult,
)
from app.platform.interaction.domain.agent_call import AgentCallResult, StructuredAgentCall
from app.platform.interaction.domain.attachment import ResolvedAttachment
from app.platform.interaction.ports.mcp_dispatch import McpDispatchScope
from app.platform.security import (
    AnonymousPrincipalResolver,
    PrincipalResolutionContext,
    PrincipalResolverPort,
    RequestPrincipal,
)
from app.shared.config import settings

TENDER_MCP_SERVER_NAME = "tender-agent"
TENDER_MCP_TOOL_NAME = "tender.generate_bid_skeleton"
TENDER_MCP_EXTRACT_TOOL_NAME = "tender.extract_bid_format_section"
TENDER_MCP_VERIFY_TOOL_NAME = "tender.verify_extraction_boundary"
TENDER_MCP_MOUNT_PATH = "/api/v1/mcp/tender"
_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

McpDispatchScopeProvider = Callable[
    [RequestPrincipal], AbstractContextManager[McpDispatchScope]
]


class _McpProjectionError(ValueError):
    """MCP 结果投影失败，不应被误报为客户端输入错误。"""


def create_tender_mcp_server(
    scope_provider: McpDispatchScopeProvider,
    *,
    principal_resolver: PrincipalResolverPort | None = None,
) -> FastMCP:
    """创建只负责协议适配的 Tender MCP Server。"""

    resolver = principal_resolver or AnonymousPrincipalResolver()
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
        ctx: Context | None = None,
    ) -> CallToolResult:
        try:
            content = _decode_and_validate(file_name, content_base64)
        except ValueError as exc:
            return _error_result("INVALID_INPUT", str(exc))

        def project(result: AgentCallResult, scope: McpDispatchScope) -> CallToolResult:
            output = result.output
            metadata, resources = _project_artifacts(
                output.get("artifacts"),
                storage=scope.attachment_storage,
                principal=scope.principal,
            )
            structured = {
                "analysis": output.get("analysis", {}),
                "artifacts": metadata,
                "model": output.get("model"),
                "prompt_version": output.get("prompt_version"),
            }
            return _resource_result(structured, resources)

        return _execute_mcp_call(
            scope_provider,
            resolver,
            ctx,
            capability_code="tender.generate_bid_skeleton",
            inputs={"source_document": (file_name, content), "user_focus": user_focus},
            project=project,
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
        ctx: Context | None = None,
    ) -> CallToolResult:
        try:
            content = _decode_and_validate(file_name, content_base64)
        except ValueError as exc:
            return _error_result("INVALID_INPUT", str(exc))

        def project(result: AgentCallResult, scope: McpDispatchScope) -> CallToolResult:
            structured = {
                "start_block_id": result.output.get("start_block_id"),
                "end_block_id": result.output.get("end_block_id"),
                "block_count": result.output.get("block_count"),
                "table_count": result.output.get("table_count"),
            }
            artifact, resources = _project_artifact(
                result.output.get("artifact"),
                storage=scope.attachment_storage,
                principal=scope.principal,
            )
            structured["artifact"] = artifact
            return _resource_result(structured, [resources])

        return _execute_mcp_call(
            scope_provider,
            resolver,
            ctx,
            capability_code="tender.extract_bid_format_section",
            inputs={
                "source_document": (file_name, content),
                "start_block_id": start_block_id,
                "end_block_id": end_block_id,
                "output_name": output_name,
            },
            project=project,
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
        ctx: Context | None = None,
    ) -> CallToolResult:
        try:
            content = _decode_and_validate(file_name, content_base64)
        except ValueError as exc:
            return _error_result("INVALID_INPUT", str(exc))

        def project(result: AgentCallResult, scope: McpDispatchScope) -> CallToolResult:
            del scope
            return CallToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(result.output, ensure_ascii=False))
                ],
                structuredContent=result.output,
            )

        return _execute_mcp_call(
            scope_provider,
            resolver,
            ctx,
            capability_code="tender.verify_extraction_boundary",
            inputs={
                "source_document": (file_name, content),
                "start_block_id": start_block_id,
                "end_block_id": end_block_id,
                "context_radius": context_radius,
            },
            project=project,
        )

    return server


def _execute_mcp_call(
    scope_provider: McpDispatchScopeProvider,
    resolver: PrincipalResolverPort,
    ctx: Context | None,
    *,
    capability_code: str,
    inputs: dict[str, object],
    project: Callable[[AgentCallResult, McpDispatchScope], CallToolResult],
) -> CallToolResult:
    try:
        principal = resolver.resolve(
            PrincipalResolutionContext(headers=_context_headers(ctx))
        )
    except Exception:  # noqa: BLE001 - protocol boundary must not leak resolver details
        return _error_result("AUTHENTICATION_REQUIRED", "MCP 请求主体不可用。")

    if not principal.authenticated or not principal.subject:
        return _error_result("AUTHENTICATION_REQUIRED", "MCP 请求需要可信主体。")

    access_context = AttachmentAccessContext(subject=principal.subject)
    try:
        with scope_provider(principal) as scope:
            source_document = inputs.get("source_document")
            if not isinstance(source_document, tuple) or len(source_document) != 2:
                return _error_result("INVALID_INPUT", "招标文件输入无效。")
            file_name, content = source_document
            reference = scope.attachment_storage.stage_attachment(
                file_name=file_name,
                media_type=_DOCX_MEDIA_TYPE,
                file_stream=_bytes_stream(content),
                context=access_context,
            )
            try:
                dispatched: AgentCallDispatchResult | None = None
                internal_inputs = dict(inputs)
                internal_inputs["source_document"] = ResolvedAttachment(
                    reference=reference,
                    content=content,
                )
                call = StructuredAgentCall(
                    call_id=uuid4().hex,
                    capability_code=capability_code,
                    run_id=uuid4().hex,
                    inputs=internal_inputs,
                )
                dispatched = scope.dispatcher.dispatch(
                    AgentCallDispatchCommand(call=call, principal=scope.principal)
                )
                if dispatched.status == "accepted":
                    return _accepted_result(dispatched)
                if dispatched.status != "completed" or dispatched.result is None:
                    return _dispatch_error_result(dispatched)
                return project(dispatched.result, scope)
            finally:
                if dispatched is None or dispatched.status != "accepted":
                    _discard_storage(
                        scope.attachment_storage,
                        scope.principal,
                        reference.attachment_id,
                    )
    except _McpProjectionError:
        return _error_result("INTERNAL_ERROR", "Tender 输出资源暂时无法读取。")
    except ValueError as exc:
        return _error_result("INVALID_INPUT", str(exc))
    except Exception:  # noqa: BLE001 - protocol boundary must not leak internals
        return _error_result("INTERNAL_ERROR", "Tender Agent 处理失败。")


def _decode_and_validate(file_name: str, value: str) -> bytes:
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("招标文件名称不能为空。")
    if not file_name.lower().endswith(".docx"):
        raise ValueError("Tender 只接受 DOCX 招标文件。")
    try:
        content = base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ValueError("文件内容不是有效的 Base64。") from exc
    if not content:
        raise ValueError("招标文件不能为空。")
    if len(content) > settings.tender_upload_max_size_bytes:
        raise ValueError("招标文件超过统一入口大小限制。")
    return content


def _bytes_stream(content: bytes):  # noqa: ANN202
    from io import BytesIO

    return BytesIO(content)


def _context_headers(ctx: Context | None) -> dict[str, str]:
    if ctx is None:
        return {}
    try:
        request = ctx.request_context.request
        headers = getattr(request, "headers", None)
        return {str(key): str(value) for key, value in headers.items()} if headers else {}
    except Exception:  # noqa: BLE001 - absent framework request context is anonymous
        return {}


def _project_artifacts(
    value: object,
    *,
    storage: AttachmentStoragePort,
    principal: RequestPrincipal,
) -> tuple[list[dict[str, object]], list[EmbeddedResource]]:
    if not isinstance(value, list):
        raise _McpProjectionError("Tender 输出文件列表无效。")
    metadata: list[dict[str, object]] = []
    resources: list[EmbeddedResource] = []
    for item in value:
        item_metadata, resource = _project_artifact(
            item,
            storage=storage,
            principal=principal,
        )
        metadata.append(item_metadata)
        resources.append(resource)
    return metadata, resources


def _project_artifact(
    value: object,
    *,
    storage: AttachmentStoragePort,
    principal: RequestPrincipal,
) -> tuple[dict[str, object], EmbeddedResource]:
    if not isinstance(value, Mapping):
        raise _McpProjectionError("Tender 输出文件无效。")
    resource_id = value.get("resource_id")
    file_name = value.get("file_name")
    media_type = value.get("media_type")
    if not isinstance(resource_id, str) or not isinstance(file_name, str):
        raise _McpProjectionError("Tender 输出资源引用无效。")
    if not isinstance(media_type, str) or not media_type.strip():
        raise _McpProjectionError("Tender 输出媒体类型无效。")
    read_result = storage.read(
        resource_id,
        context=AttachmentAccessContext(subject=principal.subject or ""),
    )
    try:
        if read_result.status != "available" or read_result.content is None:
            raise _McpProjectionError("Tender 输出资源暂时不可用。")
        metadata = {
            "file_name": file_name,
            "media_type": media_type,
            "size_bytes": len(read_result.content),
            "resource_uri": _artifact_uri(file_name),
        }
        resource = EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=_artifact_uri(file_name),
                mimeType=media_type,
                blob=base64.b64encode(read_result.content).decode("ascii"),
            ),
        )
        return metadata, resource
    finally:
        _discard_storage(storage, principal, resource_id)


def _resource_result(
    structured: dict[str, object],
    resources: list[EmbeddedResource],
) -> CallToolResult:
    content_blocks: list[Any] = [
        TextContent(type="text", text=json.dumps(structured, ensure_ascii=False)),
        *resources,
    ]
    return CallToolResult(content=content_blocks, structuredContent=structured)


def _accepted_result(dispatched: AgentCallDispatchResult) -> CallToolResult:
    """MCP 只返回受控引用；异步结果不在本协议内投影文件内容。"""

    structured = {
        "status": "accepted",
        "execution_reference": dispatched.execution_reference,
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(structured, ensure_ascii=False))],
        structuredContent=structured,
    )


def _artifact_uri(file_name: str) -> str:
    safe_name = PurePosixPath(file_name).name.replace(" ", "_")
    return f"tender://artifacts/{safe_name}"


def _dispatch_error_result(dispatched: AgentCallDispatchResult) -> CallToolResult:
    error = dispatched.error
    code = error.error_code if error else "INTERNAL_ERROR"
    message = error.message if error else "Tender Agent 处理失败。"
    mapped_code, mapped_message = _map_dispatch_error(code, message)
    return _error_result(mapped_code, mapped_message)


def _map_dispatch_error(code: str, message: str) -> tuple[str, str]:
    del message
    known = {
        "INVALID_INPUT": ("INVALID_INPUT", "输入不符合 Tender 工具要求。"),
        "DOCUMENT_PARSE_FAILED": ("DOCUMENT_PARSE_FAILED", "招标 DOCX 解析失败。"),
        "SERVICE_NOT_CONFIGURED": (
            "SERVICE_NOT_CONFIGURED",
            "Tender Agent 的模型服务尚未完成配置。",
        ),
        "UPSTREAM_FAILED": ("UPSTREAM_FAILED", "Tender Agent 的模型服务调用失败。"),
        "ANALYSIS_FAILED": ("ANALYSIS_FAILED", "招标文件结构化分析结果无效。"),
        "RENDER_FAILED": ("RENDER_FAILED", "投标骨架文件生成失败。"),
        "INPUT_VALIDATION_FAILED": ("INVALID_INPUT", "输入不符合当前 Tender 能力契约。"),
        "DISPATCH_INPUT_INVALID": ("INVALID_INPUT", "输入不符合当前 Tender 能力契约。"),
        "CAPABILITY_UNAVAILABLE": ("CAPABILITY_UNAVAILABLE", "Tender 能力当前不可用。"),
        "CAPABILITY_CATALOG_UNAVAILABLE": (
            "CAPABILITY_UNAVAILABLE",
            "Tender 能力目录当前不可用。",
        ),
        "CAPABILITY_TYPE_NOT_AGENT": ("CAPABILITY_UNAVAILABLE", "Tender 能力当前不可用。"),
        "AUTHENTICATION_REQUIRED": ("AUTHENTICATION_REQUIRED", "MCP 请求需要可信主体。"),
        "AGENT_ARTIFACT_STORE_FAILED": (
            "INTERNAL_ERROR",
            "Tender 输出文件暂时无法保存。",
        ),
    }
    return known.get(code, ("INTERNAL_ERROR", "Tender Agent 处理失败。"))


def _error_result(code: str, message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=f"{code}: {message}")],
        structuredContent={"error_code": code, "message": message},
        isError=True,
    )


def _discard_storage(
    storage: AttachmentStoragePort,
    principal: RequestPrincipal,
    attachment_id: str,
) -> None:
    try:
        storage.discard(
            attachment_id,
            context=AttachmentAccessContext(subject=principal.subject or ""),
        )
    except Exception:  # noqa: BLE001 - cleanup must not change the protocol result
        pass


__all__ = [
    "TENDER_MCP_EXTRACT_TOOL_NAME",
    "TENDER_MCP_MOUNT_PATH",
    "TENDER_MCP_SERVER_NAME",
    "TENDER_MCP_TOOL_NAME",
    "TENDER_MCP_VERIFY_TOOL_NAME",
    "create_tender_mcp_server",
]
