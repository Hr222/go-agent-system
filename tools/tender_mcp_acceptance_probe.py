"""通过真实 MCP Streamable HTTP 入口运行 Tender V1 验收探针。"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import BlobResourceContents, EmbeddedResource

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.interfaces.agent.tender_mcp import TENDER_MCP_TOOL_NAME

DEFAULT_ENDPOINT = "http://127.0.0.1:9205/api/v1/mcp/tender/mcp"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="真实 DOCX 招标文件")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--focus", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    output_dir = args.output_dir or (
        Path("tmp") / "tender-mcp-acceptance" / _safe_name(args.source.stem)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "status": "failed",
        "entrypoint": "mcp_streamable_http",
        "tool": TENDER_MCP_TOOL_NAME,
        "endpoint": args.endpoint,
        "source_name": args.source.name,
        "output_dir": str(output_dir.resolve()),
    }

    try:
        source_content = args.source.read_bytes()
        response = asyncio.run(
            _call_mcp_tool(
                endpoint=args.endpoint,
                file_name=args.source.name,
                content=source_content,
                user_focus=args.focus,
            )
        )
        record.update(
            _save_response(
                response=response,
                output_dir=output_dir,
                source_bytes=len(source_content),
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI reports a bounded diagnostic
        record.update(
            {
                "source_bytes": args.source.stat().st_size
                if args.source.exists()
                else None,
                "exception_type": f"{type(exc).__module__}.{type(exc).__name__}",
                "message": str(exc)[:300],
            }
        )

    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["status"] == "ok" else 1


async def _call_mcp_tool(
    *,
    endpoint: str,
    file_name: str,
    content: bytes,
    user_focus: str | None,
) -> object:
    arguments: dict[str, object] = {
        "file_name": file_name,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
    if user_focus and user_focus.strip():
        arguments["user_focus"] = user_focus.strip()

    async with httpx.AsyncClient(timeout=None) as http_client:
        async with streamable_http_client(
            endpoint,
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.call_tool(TENDER_MCP_TOOL_NAME, arguments)


def _save_response(
    *,
    response: object,
    output_dir: Path,
    source_bytes: int,
) -> dict[str, object]:
    is_error = bool(getattr(response, "isError", False))
    structured = getattr(response, "structuredContent", None)
    if not isinstance(structured, dict):
        structured = {}

    artifact_metadata = structured.get("artifacts", [])
    if not isinstance(artifact_metadata, list):
        artifact_metadata = []
    saved_artifacts: list[dict[str, object]] = []
    for content_block in getattr(response, "content", []):
        if not isinstance(content_block, EmbeddedResource):
            continue
        resource = content_block.resource
        if not isinstance(resource, BlobResourceContents):
            continue
        resource_uri = str(resource.uri)
        decoded_resource_uri = unquote(resource_uri)
        metadata = next(
            (
                item
                for item in artifact_metadata
                if isinstance(item, dict)
                and unquote(str(item.get("resource_uri"))) == decoded_resource_uri
            ),
            {},
        )
        file_name = Path(
            str(metadata.get("file_name") or decoded_resource_uri.rsplit("/", 1)[-1])
        ).name
        file_path = output_dir / file_name
        file_content = base64.b64decode(resource.blob, validate=True)
        file_path.write_bytes(file_content)
        saved_artifacts.append(
            {
                "file_name": file_name,
                "path": str(file_path.resolve()),
                "bytes": len(file_content),
                "media_type": resource.mimeType,
            }
        )

    analysis = structured.get("analysis")
    if not isinstance(analysis, dict):
        analysis = None
    error = {
        "error_code": structured.get("error_code"),
        "message": structured.get("message"),
    }
    return {
        "status": "failed" if is_error else "ok",
        "source_bytes": source_bytes,
        "analysis": analysis,
        "artifacts": artifact_metadata,
        "saved_artifacts": saved_artifacts,
        "error": error if is_error else None,
    }


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("._")
    return normalized or "sample"


if __name__ == "__main__":
    raise SystemExit(main())
