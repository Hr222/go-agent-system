from __future__ import annotations

from app.modules.llm.ports import TextEmbeddingPort

# 兼容现有组装代码；领域映射由 Ingestion 流水线负责。
ChunkEmbeddingPort = TextEmbeddingPort
