"""入库重试所需的来源端口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class IngestionRetrySource:
    source_path: str
    policy_category: str
    responsible_department: str | None
    version_label: str | None
    target_document_id: int


class IngestionRetrySourcePort(Protocol):
    def get_retry_source(self, document_id: int) -> IngestionRetrySource | None: ...

