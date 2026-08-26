from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from app.platform.interaction.domain.capability import PlatformCapability
from app.platform.interaction.domain.intent import validate_capability_inputs
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort

AgentExecutionHandler = Callable[[dict[str, object]], object]


class AgentRuntime:
    """只消费平台目录中的 Agent 条目，不维护第二份注册表。"""

    def __init__(
        self,
        capability_catalog: CapabilityCatalogPort,
        handlers: Mapping[str, AgentExecutionHandler] | None = None,
    ) -> None:
        self.capability_catalog = capability_catalog
        self._handlers = dict(handlers or {})

    def list_capabilities(
        self,
        *,
        permissions: Iterable[str] = (),
    ) -> tuple[PlatformCapability, ...]:
        return self.capability_catalog.list_available(
            capability_type="agent",
            permissions=permissions,
        )

    def get_capability(
        self,
        code: str,
        *,
        permissions: Iterable[str] = (),
    ) -> PlatformCapability | None:
        capability = self.capability_catalog.get_available(code, permissions=permissions)
        if capability is None or capability.capability_type != "agent":
            return None
        return capability

    def execute(
        self,
        *,
        capability_code: str,
        dispatch_key: str,
        inputs: dict[str, object],
        permissions: Iterable[str] = (),
    ) -> object:
        """Execute only a current, authorized Agent catalog entry."""

        permission_tuple = tuple(permissions)
        capability = self.get_capability(
            capability_code,
            permissions=permission_tuple,
        )
        if capability is None or capability.dispatch_key != dispatch_key:
            raise LookupError("Agent capability is unavailable for the current request")

        validation = validate_capability_inputs(capability, inputs)
        if not validation.valid:
            raise ValueError("Agent capability inputs do not match the catalog contract")

        handler = self._handlers.get(dispatch_key)
        if handler is None:
            raise LookupError("Agent execution target is not configured")
        return handler(dict(inputs))
