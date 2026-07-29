from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def serialize_sse_event(event: str, data: Mapping[str, Any]) -> str:
    """将一个结构化事件编码为浏览器可解析的 SSE 帧。"""

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
