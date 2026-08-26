from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True, frozen=True)
class KnowledgeAuditIssue:
    """一条可重复定位的知识库质量问题。"""

    code: str
    severity: str
    entity_type: str
    entity_id: int | None
    message: str
    details: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class KnowledgeQualityAuditReport:
    """知识库只读审计结果，不包含任何清理或修改动作。"""

    document_count: int
    version_count: int
    section_count: int
    block_count: int
    chunk_count: int
    document_status_counts: dict[str, int]
    version_status_counts: dict[str, int]
    parser_status_counts: dict[str, int]
    current_version_count: int
    latest_version_count: int
    issues: tuple[KnowledgeAuditIssue, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def issue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.code] = counts.get(issue.code, 0) + 1
        return dict(sorted(counts.items()))


class KnowledgeQualityAuditPort(Protocol):
    """知识库质量审计所需的只读能力。"""

    def audit(self) -> KnowledgeQualityAuditReport: ...
