from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class KnowledgeVersionRef:
    """知识版本在发布流程中的最小领域标识。"""

    document_id: int
    version_id: int
