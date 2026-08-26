from __future__ import annotations

from dataclasses import dataclass

from app.platform.interaction.domain.capability import (
    CapabilityType,
    PlatformCapability,
    validate_capability,
    validate_dispatch_key,
)


class CapabilityDispatchConfigurationError(ValueError):
    """目录分发键没有对应受控 Use Case。"""


@dataclass(frozen=True, slots=True)
class CapabilityDispatchBinding:
    """Composition Root 中声明的固定分发目标类型。"""

    dispatch_key: str
    capability_type: CapabilityType
    use_case_type: type[object]


class CapabilityDispatchRegistry:
    """只负责校验目录分发键，不执行 Use Case。"""

    def __init__(self, bindings: tuple[CapabilityDispatchBinding, ...] = ()) -> None:
        self._bindings: dict[str, CapabilityDispatchBinding] = {}
        for binding in bindings:
            self.register(binding)

    def register(self, binding: CapabilityDispatchBinding) -> None:
        if binding.dispatch_key in self._bindings:
            raise CapabilityDispatchConfigurationError(
                f"分发键重复注册：{binding.dispatch_key}。"
            )
        try:
            validate_dispatch_key(binding.dispatch_key)
        except ValueError as exc:
            raise CapabilityDispatchConfigurationError(str(exc)) from exc
        if not isinstance(binding.use_case_type, type):
            raise CapabilityDispatchConfigurationError(
                f"分发键 {binding.dispatch_key} 没有绑定固定 Use Case 类型。"
            )
        self._bindings[binding.dispatch_key] = binding

    def validate(self, capability: PlatformCapability) -> CapabilityDispatchBinding:
        validate_capability(capability)
        binding = self._bindings.get(capability.dispatch_key)
        if binding is None:
            raise CapabilityDispatchConfigurationError(
                f"能力 {capability.code} 的分发键未注册：{capability.dispatch_key}。"
            )
        if binding.capability_type != capability.capability_type:
            raise CapabilityDispatchConfigurationError(
                f"能力 {capability.code} 的类型 {capability.capability_type} 与分发键 "
                f"{capability.dispatch_key} 的类型 {binding.capability_type} 不匹配。"
            )
        return binding

    def contains(self, dispatch_key: str) -> bool:
        return dispatch_key in self._bindings
