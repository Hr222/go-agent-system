from __future__ import annotations

from collections.abc import Iterable

from app.modules.interaction.domain.candidate import (
    CandidateIndexError,
    CandidateRetrievalStatus,
    CapabilityCandidate,
    CapabilityCandidateIndexEntry,
    CapabilityCandidateRetrievalResult,
    CapabilityIndexBuildResult,
    IndexBuildStatus,
    cosine_similarity,
)
from app.modules.interaction.domain.capability import PlatformCapability
from app.modules.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.modules.llm.ports import TextEmbeddingPort


class InMemoryCapabilityCandidateIndex:
    """能力候选的进程内索引，不依赖数据库或知识库检索对象。"""

    def __init__(self) -> None:
        self._entries: dict[str, CapabilityCandidateIndexEntry] = {}
        self._built = False

    @property
    def is_ready(self) -> bool:
        return self._built

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def replace(self, entries: Iterable[CapabilityCandidateIndexEntry]) -> None:
        replacement: dict[str, CapabilityCandidateIndexEntry] = {}
        for entry in entries:
            if entry.capability_code in replacement:
                raise CandidateIndexError(f"候选索引包含重复能力代码：{entry.capability_code}。")
            replacement[entry.capability_code] = entry
        self._entries = replacement
        self._built = True

    def search(
        self,
        query_vector: tuple[float, ...],
        *,
        top_k: int,
        min_score: float,
    ) -> tuple[CapabilityCandidate, ...]:
        if top_k < 1:
            raise ValueError("候选数量上限必须为正整数。")
        scored = []
        for entry in self._entries.values():
            score = cosine_similarity(query_vector, entry.vector)
            if score >= min_score:
                scored.append(
                    CapabilityCandidate(
                        capability_code=entry.capability_code,
                        score=score,
                        retrieval_metadata=dict(entry.retrieval_metadata),
                    )
                )
        scored.sort(key=lambda candidate: (-candidate.score, candidate.capability_code))
        return tuple(scored[:top_k])


class CapabilityCandidateRetrieval:
    """从能力目录构建候选索引并返回有限候选。"""

    DEFAULT_TOP_K = 5
    MAX_TOP_K = 50

    def __init__(
        self,
        capability_catalog: CapabilityCatalogPort,
        embedding: TextEmbeddingPort,
        *,
        index: InMemoryCapabilityCandidateIndex | None = None,
        default_min_score: float = 0.0,
    ) -> None:
        if not -1.0 <= default_min_score <= 1.0:
            raise ValueError("默认候选相似度阈值必须在 -1 到 1 之间。")
        self.capability_catalog = capability_catalog
        self.embedding = embedding
        self.index = index or InMemoryCapabilityCandidateIndex()
        self.default_min_score = default_min_score

    def refresh(self, *, permissions: Iterable[str] = ()) -> CapabilityIndexBuildResult:
        """从当前启用目录重建索引；失败时保留原索引，不降级为全量目录。"""

        try:
            capabilities = self.capability_catalog.list_available(permissions=permissions)
            search_texts = [build_search_text(capability) for capability in capabilities]
            vectors = self.embedding.embed_texts(search_texts)
            if len(vectors) != len(capabilities):
                raise CandidateIndexError("Embedding 返回数量与能力目录数量不一致。")
            entries = [
                CapabilityCandidateIndexEntry(
                    capability_code=capability.code,
                    search_text=search_text,
                    vector=tuple(vector),
                    retrieval_metadata=dict(capability.retrieval_metadata),
                )
                for capability, search_text, vector in zip(
                    capabilities,
                    search_texts,
                    vectors,
                )
            ]
            self.index.replace(entries)
        except Exception as exc:  # noqa: BLE001 - 候选索引边界统一转换
            return CapabilityIndexBuildResult(
                status="failed",
                indexed_count=self.index.entry_count,
                error_code="INDEX_BUILD_FAILED",
                error_message=str(exc),
            )

        status: IndexBuildStatus = "ready" if capabilities else "empty"
        return CapabilityIndexBuildResult(
            status=status,
            indexed_count=len(capabilities),
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        min_score: float | None = None,
    ) -> CapabilityCandidateRetrievalResult:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("候选召回查询不能为空。")
        if top_k < 1 or top_k > self.MAX_TOP_K:
            raise ValueError(f"候选数量上限必须在 1 到 {self.MAX_TOP_K} 之间。")
        threshold = self.default_min_score if min_score is None else min_score
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("候选相似度阈值必须在 -1 到 1 之间。")
        if not self.index.is_ready:
            return CapabilityCandidateRetrievalResult(
                query=normalized_query,
                status="unavailable",
                error_code="INDEX_UNAVAILABLE",
                error_message="能力候选索引尚未成功构建。",
            )

        try:
            query_vector = tuple(self.embedding.embed_text(normalized_query))
            candidates = self.index.search(
                query_vector,
                top_k=top_k,
                min_score=threshold,
            )
        except Exception as exc:  # noqa: BLE001 - 候选查询边界统一转换
            return CapabilityCandidateRetrievalResult(
                query=normalized_query,
                status="unavailable",
                error_code="EMBEDDING_UNAVAILABLE",
                error_message=str(exc),
            )

        status: CandidateRetrievalStatus = "ready" if candidates else "empty"
        return CapabilityCandidateRetrievalResult(
            query=normalized_query,
            status=status,
            candidates=candidates,
        )


def build_search_text(capability: PlatformCapability) -> str:
    """把目录描述和正向检索语料拼成独立候选索引文本。"""

    parts = [capability.code, capability.description]
    metadata = capability.retrieval_metadata
    for key in ("aliases", "keywords", "examples", "positive_examples", "search_terms"):
        value = metadata.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value if str(item).strip())
    return "\n".join(part.strip() for part in parts if part.strip())
