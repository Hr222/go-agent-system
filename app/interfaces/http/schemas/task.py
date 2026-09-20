from __future__ import annotations

from datetime import datetime
from typing import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskResponse(BaseModel):
    id: UUID
    task_type: str
    owner_subject: str
    status: str
    attempt_count: int
    max_attempts: int
    available_at: datetime
    result_summary: str | None = None
    failure_code: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskPageResponse(BaseModel):
    tasks: list[TaskResponse]
    has_more: bool
    next_cursor: str | None


class TaskEventResponse(BaseModel):
    id: UUID
    sequence: int
    transition_id: str
    event_type: str
    metadata: Mapping[str, str | int]
    created_at: datetime


class TaskEventPageResponse(BaseModel):
    events: list[TaskEventResponse]
    has_more: bool
    next_after_sequence: int | None


class TaskCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1, max_length=128)

    @field_validator("command_id", mode="before")
    @classmethod
    def validate_command_id(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("command_id 不能为空白。")
        return value.strip()
