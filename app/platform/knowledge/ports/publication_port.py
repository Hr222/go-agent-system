from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class KnowledgePublicationRecord:
    """知识版本发布后的应用层结果。"""

    document_id: int
    version_id: int
    version_status: str


class KnowledgePublicationPort(Protocol):
    """知识版本发布/激活端口。"""

    def activate_version(
        self,
        *,
        document_id: int,
        version_id: int,
    ) -> KnowledgePublicationRecord: ...
