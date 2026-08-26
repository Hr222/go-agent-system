from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ChecklistDataFieldTrace:
    """记录单个业务输入字段的来源、是否提供与值数量。"""

    field_key: str
    label: str
    source: str
    provided: bool
    value_count: int


@dataclass(slots=True, frozen=True)
class ChecklistDataPack:
    """统一承载数据层输出，供后续决策层复用。"""

    scenario_code: str
    provider_name: str
    submitted_materials: tuple[str, ...]
    field_traces: tuple[ChecklistDataFieldTrace, ...]
    provided_input_fields: tuple[str, ...]
    missing_input_fields: tuple[str, ...]
    insufficient_reason: str | None

    @property
    def is_sufficient(self) -> bool:
        return not self.missing_input_fields
