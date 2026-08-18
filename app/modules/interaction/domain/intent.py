from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.interaction.domain.capability import PlatformCapability

IntentAssessmentStatus = Literal["matched", "needs_clarification", "unrecognized"]


class IntentAssessment(BaseModel):
    """候选范围内的结构化意图评估，不代表执行授权。"""

    status: IntentAssessmentStatus
    capability_code: str | None = None
    extracted_inputs: dict[str, object] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    clarification: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    candidate_codes: list[str] = Field(default_factory=list)
    error_code: str | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class InputValidationResult:
    """能力输入的确定性校验结果。"""

    missing_fields: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not (self.missing_fields or self.unknown_fields or self.invalid_fields)


def validate_capability_inputs(
    capability: PlatformCapability,
    inputs: Mapping[str, object],
) -> InputValidationResult:
    """按目录中的输入 Schema 二次校验模型提取结果。"""

    properties = capability.input_schema.get("properties")
    declared_properties = properties if isinstance(properties, Mapping) else {}
    allows_additional = capability.input_schema.get("additionalProperties") is True
    unknown_fields = ()
    if not allows_additional:
        unknown_fields = tuple(sorted(set(inputs) - set(declared_properties)))

    invalid_fields = tuple(
        sorted(
            field_name
            for field_name, value in inputs.items()
            if field_name in declared_properties
            and not _matches_schema_type(value, declared_properties[field_name])
        )
    )
    missing_fields = tuple(
        field_name
        for field_name in capability.required_fields
        if field_name not in inputs or _is_missing_value(inputs[field_name])
    )
    return InputValidationResult(
        missing_fields=missing_fields,
        unknown_fields=unknown_fields,
        invalid_fields=invalid_fields,
    )


def _matches_schema_type(value: object, schema: object) -> bool:
    if not isinstance(schema, Mapping):
        return True
    expected_type = schema.get("type")
    if expected_type is None:
        return True
    expected_types = (expected_type,) if isinstance(expected_type, str) else tuple(expected_type)
    return any(_matches_json_type(value, item) for item in expected_types)


def _matches_json_type(value: object, expected_type: object) -> bool:
    return {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "null": value is None,
    }.get(expected_type, True)


def _is_missing_value(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []
