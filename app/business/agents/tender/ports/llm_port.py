"""兼容旧导入路径；通用结构化 LLM 契约属于 `modules.llm`。"""

from __future__ import annotations

from app.platform.llm.contracts import (
    StructuredLlmPort,
    StructuredLlmRequest,
    StructuredLlmResult,
)

__all__ = ["StructuredLlmPort", "StructuredLlmRequest", "StructuredLlmResult"]
