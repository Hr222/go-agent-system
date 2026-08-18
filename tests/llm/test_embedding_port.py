from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure.llm.embedding_client import GiteeEmbeddingClient
from app.shared.config import settings
from app.shared.exceptions import UpstreamServiceError


class FakeEmbeddings:
    def __init__(self, vectors: list[list[float]] | None = None, error: Exception | None = None):
        self.vectors = vectors or []
        self.error = error
        self.calls: list[list[str]] = []
        self._next_vector = 0

    def create(self, *, model: str, input: list[str], dimensions: int) -> SimpleNamespace:
        self.calls.append(input)
        if self.error is not None:
            raise self.error
        batch = self.vectors[self._next_vector : self._next_vector + len(input)]
        self._next_vector += len(input)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=vector) for vector in batch]
        )


class FakeClient:
    def __init__(self, embeddings: FakeEmbeddings):
        self.embeddings = embeddings


def test_embed_text_returns_the_single_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vector_dimensions", 2)
    embeddings = FakeEmbeddings(vectors=[[0.25, 0.75]])
    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    result = client.embed_text(" one text ")

    assert result == [0.25, 0.75]
    assert embeddings.calls == [["one text"]]


def test_embed_texts_preserves_input_order_and_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vector_dimensions", 2)
    monkeypatch.setattr(settings, "embedding_batch_size", 2)
    embeddings = FakeEmbeddings(
        vectors=[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
    )

    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    result = client.embed_texts([" first ", "second", "third"])

    assert result == [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    assert embeddings.calls == [["first", "second"], ["third"]]


def test_embed_texts_rejects_blank_text_without_calling_provider() -> None:
    embeddings = FakeEmbeddings(vectors=[[1.0, 0.0]])
    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    with pytest.raises(ValueError, match="不能为空"):
        client.embed_texts(["valid", "   "])

    assert embeddings.calls == []


def test_embed_texts_rejects_incomplete_provider_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vector_dimensions", 2)
    embeddings = FakeEmbeddings(vectors=[[1.0, 0.0]])
    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    with pytest.raises(RuntimeError, match="数量不一致"):
        client.embed_texts(["first", "second"])


def test_embed_texts_rejects_wrong_vector_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vector_dimensions", 2)
    embeddings = FakeEmbeddings(vectors=[[1.0]])
    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    with pytest.raises(RuntimeError, match="维度不匹配"):
        client.embed_texts(["text"])


def test_embed_texts_maps_provider_failure() -> None:
    embeddings = FakeEmbeddings(error=TimeoutError("timed out"))
    client = GiteeEmbeddingClient(client=FakeClient(embeddings))

    with pytest.raises(UpstreamServiceError, match="请求失败"):
        client.embed_texts(["text"])
