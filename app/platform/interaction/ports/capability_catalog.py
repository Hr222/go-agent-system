from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.platform.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    PlatformCapability,
)


class CapabilityCatalogPort(Protocol):
    """交互层消费平台能力目录的只读端口。"""

    def list_available(
        self,
        *,
        capability_type: CapabilityType | None = None,
        permissions: Iterable[str] = (),
    ) -> tuple[PlatformCapability, ...]: ...

    def get_available(
        self,
        code: str,
        *,
        permissions: Iterable[str] = (),
    ) -> PlatformCapability | None: ...


class CapabilityCatalogRepositoryPort(Protocol):
    """能力目录 Repository 的持久化端口。"""

    def list_registered(self) -> tuple[PlatformCapability, ...]: ...

    def list_available(
        self,
        *,
        capability_type: CapabilityType | None = None,
        principal: CapabilityPrincipal | None = None,
    ) -> tuple[PlatformCapability, ...]: ...

    def get_available(
        self,
        code: str,
        *,
        principal: CapabilityPrincipal | None = None,
    ) -> PlatformCapability | None: ...
