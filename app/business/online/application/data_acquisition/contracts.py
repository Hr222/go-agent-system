from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.business.online.application.data_acquisition.models import ChecklistDataPack


@dataclass(slots=True, frozen=True)
class ChecklistInput:
    """材料核验所需的内部业务输入。"""

    submitted_materials: tuple[str, ...]
    provided_fields: frozenset[str]

    @classmethod
    def from_source(cls, source: object) -> "ChecklistInput":
        submitted_materials = tuple(getattr(source, "submitted_materials", ()))
        provided_fields = frozenset(getattr(source, "model_fields_set", set()))
        return cls(
            submitted_materials=submitted_materials,
            provided_fields=provided_fields,
        )


@dataclass(slots=True, frozen=True)
class ChecklistDataAcquisitionRequest:
    """统一承载数据获取阶段所需的场景与请求上下文。"""

    scenario_code: str
    checklist_request: ChecklistInput | object
    input_field_key: str = "submitted_materials"
    input_field_label: str = "已提交材料列表"

    def __post_init__(self) -> None:
        if not isinstance(self.checklist_request, ChecklistInput):
            object.__setattr__(
                self,
                "checklist_request",
                ChecklistInput.from_source(self.checklist_request),
            )


class ChecklistDataProvider(Protocol):
    """抽象业务数据来源，允许后续接入表单、数据库或外部系统。"""

    provider_name: str

    def collect(self, request: ChecklistDataAcquisitionRequest) -> ChecklistDataPack: ...
