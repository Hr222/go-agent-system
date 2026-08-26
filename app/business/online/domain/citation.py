from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AnswerCitationResult:
    ref_no: int
    document_id: int
    version_id: int
    chunk_id: int
    policy_name: str
    section_title: str | None
    page_no: int | None
    quote: str
    source_path: str | None = None
    file_name: str | None = None
