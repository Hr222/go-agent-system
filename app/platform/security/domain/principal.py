from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RequestPrincipal:
    """Trusted request identity facts consumed by capability authorization."""

    subject: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    authenticated: bool = False

    @classmethod
    def anonymous(cls) -> "RequestPrincipal":
        return cls()

    def permission_tuple(self) -> tuple[str, ...]:
        return tuple(sorted(self.permissions))

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
