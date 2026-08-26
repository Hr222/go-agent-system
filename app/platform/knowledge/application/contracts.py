from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class KnowledgeBaseOverviewResult:
    phase: str
    mvp_scope: tuple[str, ...]
    current_categories: tuple[str, ...]
    current_focus: str
    next_focus: str


@dataclass(slots=True, frozen=True)
class RagMvpStatusResult:
    indexing_table_ready: bool
    sample_categories: tuple[str, ...]
    backend_goal: str
    frontend_goal: str
    evaluation_goal: str
