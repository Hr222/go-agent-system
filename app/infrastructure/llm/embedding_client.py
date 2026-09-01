from __future__ import annotations

from collections.abc import Sequence
from math import ceil

from openai import OpenAI

from app.platform.llm.ports import TextEmbeddingPort
from app.shared.config import settings
from app.shared.exceptions import UpstreamServiceError
from app.shared.logging import get_logger

logger = get_logger("app.infrastructure.embedding")


class GiteeEmbeddingClient(TextEmbeddingPort):
    """Gitee embedding 技术适配器。"""

    def __init__(self, client: OpenAI | None = None) -> None:
        if client is not None:
            self.client = client
        else:
            if not settings.gitee_api_key:
                raise RuntimeError("执行向量生成前必须先配置 GITEE_API_KEY。")
            self.client = OpenAI(
                api_key=settings.gitee_api_key,
                base_url=settings.gitee_base_url,
                default_headers={"X-Failover-Enabled": "true"},
            )

    def embed_query(self, text: str) -> list[float]:
        return self.embed_text(text)

    def embed_text(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        if len(vectors) != 1:
            raise RuntimeError("单条 Embedding 返回数量异常。")
        return vectors[0]

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        normalized = [text.strip() for text in texts]
        if any(not text for text in normalized):
            raise ValueError("Embedding 文本不能为空。")

        embedded: list[list[float]] = []
        batch_size = max(1, settings.embedding_batch_size)
        for start in range(0, len(normalized), batch_size):
            batch = normalized[start : start + batch_size]
            vectors = self._embed_texts(batch)
            if len(vectors) != len(batch):
                raise RuntimeError("向量返回数量与文本数量不一致。")
            for vector in vectors:
                self._validate_vector(vector)
                embedded.append(vector)
        logger.info(
            "向量生成完成 total_texts=%s batch_size=%s total_batches=%s",
            len(embedded),
            batch_size,
            ceil(len(normalized) / batch_size),
        )
        return embedded

    def close(self) -> None:
        """释放进程级 Embedding 客户端。"""

        self.client.close()

    def _validate_vector(self, vector: list[float]) -> None:
        if not isinstance(vector, list) or not all(
            isinstance(value, (int, float)) for value in vector
        ):
            raise RuntimeError("Embedding Provider 返回了无效向量。")
        if len(vector) != settings.vector_dimensions:
            raise RuntimeError(
                f"Embedding 向量维度不匹配：期望 {settings.vector_dimensions}，实际 {len(vector)}。"
            )

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
                dimensions=settings.vector_dimensions,
            )
        except Exception as exc:
            raise UpstreamServiceError(f"Gitee embedding 请求失败：{exc}") from exc
        try:
            return [list(item.embedding) for item in response.data]
        except (AttributeError, TypeError) as exc:
            raise RuntimeError("Embedding Provider 返回了无效结果。") from exc
