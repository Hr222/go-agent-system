from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.agent.tender.contracts import TenderAnalysis


class TenderArtifactResponse(BaseModel):
    file_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    content_base64: str


class TenderGenerateSkeletonResponse(BaseModel):
    analysis: TenderAnalysis
    artifacts: list[TenderArtifactResponse]
    model: str
    prompt_version: str


class TenderErrorResponse(BaseModel):
    code: str
    message: str
