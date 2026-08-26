from __future__ import annotations

from collections.abc import Iterable

from app.platform.interaction.application.dispatch import (
    CapabilityDispatchConfigurationError,
    CapabilityDispatchRegistry,
)
from app.platform.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    PlatformCapability,
)
from app.platform.interaction.ports.capability_catalog import (
    CapabilityCatalogPort,
    CapabilityCatalogRepositoryPort,
)


class PlatformCapabilityCatalog(CapabilityCatalogPort):
    """带分发键校验的目录应用服务。"""

    def __init__(
        self,
        repository: CapabilityCatalogRepositoryPort,
        dispatch_registry: CapabilityDispatchRegistry,
    ) -> None:
        self.repository = repository
        self.dispatch_registry = dispatch_registry

    def validate_registered(self) -> None:
        errors: list[str] = []
        for capability in self.repository.list_registered():
            try:
                self.dispatch_registry.validate(capability)
            except (ValueError, CapabilityDispatchConfigurationError) as exc:
                errors.append(str(exc))
        if errors:
            raise CapabilityDispatchConfigurationError(
                "平台能力目录存在不可分发记录：" + "；".join(errors)
            )

    def list_available(
        self,
        *,
        capability_type: CapabilityType | None = None,
        permissions: Iterable[str] = (),
    ) -> tuple[PlatformCapability, ...]:
        self.validate_registered()
        principal = CapabilityPrincipal.from_permissions(tuple(permissions))
        return self.repository.list_available(
            capability_type=capability_type,
            principal=principal,
        )

    def get_available(
        self,
        code: str,
        *,
        permissions: Iterable[str] = (),
    ) -> PlatformCapability | None:
        self.validate_registered()
        principal = CapabilityPrincipal.from_permissions(tuple(permissions))
        return self.repository.get_available(code, principal=principal)
