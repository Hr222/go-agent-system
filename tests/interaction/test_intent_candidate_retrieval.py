from __future__ import annotations

import ast
from pathlib import Path

from app.platform.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
)
from app.platform.interaction.domain.capability import PlatformCapability


def _capability(
    code: str,
    description: str,
    *,
    permission: tuple[str, ...] = (),
) -> PlatformCapability:
    return PlatformCapability(
        code=code,
        capability_type="chat",
        description=description,
        input_schema={},
        output_schema={},
        required_fields=(),
        confirmation_policy="always",
        permission=permission,
        enabled=True,
        timeout_seconds=120,
        error_boundary="candidate-test",
        dispatch_key=f"test.{code}",
        retrieval_metadata={"aliases": [description], "examples": [f"use {description}"]},
    )


class FakeCatalog:
    def __init__(self, capabilities: tuple[PlatformCapability, ...]) -> None:
        self.capabilities = capabilities

    def list_available(self, **kwargs):  # noqa: ANN003
        permissions = frozenset(kwargs.get("permissions", ()))
        return tuple(
            capability
            for capability in self.capabilities
            if capability.enabled and set(capability.permission).issubset(permissions)
        )

    def get_available(self, code: str, **kwargs):  # noqa: ANN003
        permissions = frozenset(kwargs.get("permissions", ()))
        return next(
            (
                item
                for item in self.capabilities
                if item.code == code
                and item.enabled
                and set(item.permission).issubset(permissions)
            ),
            None,
        )


class FakeEmbedding:
    def __init__(self) -> None:
        self.fail_batch = False
        self.fail_query = False

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail_batch:
            raise RuntimeError("batch embedding unavailable")
        return [self._vector(text) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        if self.fail_query:
            raise RuntimeError("query embedding unavailable")
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        if "high" in text or "query-high" in text:
            return [1.0, 0.0]
        if "medium" in text:
            return [0.8, 0.6]
        return [0.0, 1.0]


def test_refresh_builds_index_and_returns_sorted_candidates() -> None:
    service = CapabilityCandidateRetrieval(
        FakeCatalog(
            (
                _capability("cap.low", "low"),
                _capability("cap.high", "high"),
                _capability("cap.medium", "medium"),
            )
        ),
        FakeEmbedding(),
    )

    build_result = service.refresh()
    result = service.search("query-high")

    assert build_result.status == "ready"
    assert build_result.indexed_count == 3
    assert result.status == "ready"
    assert [item.capability_code for item in result.candidates] == [
        "cap.high",
        "cap.medium",
        "cap.low",
    ]
    assert result.candidates[0].score == 1.0
    assert result.candidates[0].retrieval_metadata["aliases"] == ["high"]


def test_default_candidate_limit_covers_registered_capabilities() -> None:
    capabilities = tuple(_capability(f"cap.{index}", "high") for index in range(7))
    service = CapabilityCandidateRetrieval(FakeCatalog(capabilities), FakeEmbedding())

    service.refresh()

    result = service.search("query-high")

    assert len(result.candidates) == 7


def test_threshold_and_empty_catalog_return_no_candidates() -> None:
    service = CapabilityCandidateRetrieval(
        FakeCatalog((_capability("cap.low", "low"),)),
        FakeEmbedding(),
    )
    service.refresh()

    result = service.search("query-high", min_score=0.9)

    assert result.status == "empty"
    assert result.candidates == ()

    empty_service = CapabilityCandidateRetrieval(FakeCatalog(()), FakeEmbedding())
    empty_build = empty_service.refresh()
    empty_result = empty_service.search("query-high")

    assert empty_build.status == "empty"
    assert empty_result.status == "empty"
    assert empty_result.candidates == ()


def test_unbuilt_index_and_query_embedding_failure_are_explicit() -> None:
    embedding = FakeEmbedding()
    service = CapabilityCandidateRetrieval(
        FakeCatalog((_capability("cap.high", "high"),)),
        embedding,
    )

    before_build = service.search("query-high")
    assert before_build.status == "unavailable"
    assert before_build.error_code == "INDEX_UNAVAILABLE"

    service.refresh()
    embedding.fail_query = True
    failed_query = service.search("query-high")

    assert failed_query.status == "unavailable"
    assert failed_query.error_code == "EMBEDDING_UNAVAILABLE"
    assert failed_query.candidates == ()


def test_index_build_failure_does_not_replace_previous_index() -> None:
    embedding = FakeEmbedding()
    catalog = FakeCatalog((_capability("cap.high", "high"),))
    service = CapabilityCandidateRetrieval(catalog, embedding)

    assert service.refresh().indexed_count == 1
    embedding.fail_batch = True
    catalog.capabilities = (_capability("cap.new", "high"),)

    failed_build = service.refresh()
    result = service.search("query-high")

    assert failed_build.status == "failed"
    assert failed_build.error_code == "INDEX_BUILD_FAILED"
    assert failed_build.indexed_count == 1
    assert [item.capability_code for item in result.candidates] == ["cap.high"]


def test_candidate_indexes_are_isolated_by_permission_scope() -> None:
    service = CapabilityCandidateRetrieval(
        FakeCatalog(
            (
                _capability("cap.public", "high"),
                _capability(
                    "cap.private",
                    "high",
                    permission=("cap:private",),
                ),
            )
        ),
        FakeEmbedding(),
    )

    private_permissions = ("cap:private",)
    assert service.refresh(permissions=private_permissions).indexed_count == 2
    assert [
        item.capability_code
        for item in service.search("query-high", permissions=private_permissions).candidates
    ] == ["cap.private", "cap.public"]

    public_before_refresh = service.search("query-high")
    assert public_before_refresh.status == "unavailable"
    assert public_before_refresh.error_code == "INDEX_UNAVAILABLE"

    assert service.refresh().indexed_count == 1
    public_result = service.search("query-high")
    assert [item.capability_code for item in public_result.candidates] == ["cap.public"]

    normalized_private_result = service.search(
        "query-high",
        permissions=(" cap:private ", "cap:private"),
    )
    assert [item.capability_code for item in normalized_private_result.candidates] == [
        "cap.private",
        "cap.public",
    ]


def test_failed_refresh_preserves_only_its_permission_scope_index() -> None:
    embedding = FakeEmbedding()
    service = CapabilityCandidateRetrieval(
        FakeCatalog(
            (
                _capability("cap.public", "high"),
                _capability(
                    "cap.private",
                    "high",
                    permission=("cap:private",),
                ),
            )
        ),
        embedding,
    )

    private_permissions = ("cap:private",)
    assert service.refresh().indexed_count == 1
    assert service.refresh(permissions=private_permissions).indexed_count == 2

    embedding.fail_batch = True
    failed_private_refresh = service.refresh(permissions=private_permissions)

    assert failed_private_refresh.status == "failed"
    assert failed_private_refresh.indexed_count == 2
    assert [
        item.capability_code
        for item in service.search("query-high", permissions=private_permissions).candidates
    ] == ["cap.private", "cap.public"]
    assert [item.capability_code for item in service.search("query-high").candidates] == [
        "cap.public"
    ]


def test_candidate_retrieval_does_not_import_policy_retrieval_components() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source_root = project_root / "app" / "platform" / "interaction"
    imported_modules: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    forbidden = ("app.platform.knowledge", "app.infrastructure.persistence")
    assert not any(module.startswith(prefix) for module in imported_modules for prefix in forbidden)
    assert "kb_policy_chunk" not in "".join(
        path.read_text(encoding="utf-8") for path in source_root.rglob("*.py")
    )
