from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models.platform_capability import PlatformCapabilityRecord
from app.modules.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    PlatformCapability,
)
from app.modules.interaction.ports.capability_catalog import CapabilityCatalogRepositoryPort


class PlatformCapabilityRepository(CapabilityCatalogRepositoryPort):
    """平台能力目录 PostgreSQL Repository。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_registered(self) -> tuple[PlatformCapability, ...]:
        records = self.session.scalars(
            select(PlatformCapabilityRecord).order_by(PlatformCapabilityRecord.code.asc())
        ).all()
        return tuple(self._to_domain(record) for record in records)

    def list_available(
        self,
        *,
        capability_type: CapabilityType | None = None,
        principal: CapabilityPrincipal | None = None,
    ) -> tuple[PlatformCapability, ...]:
        statement = (
            select(PlatformCapabilityRecord)
            .where(PlatformCapabilityRecord.enabled.is_(True))
            .order_by(PlatformCapabilityRecord.code.asc())
        )
        if capability_type is not None:
            statement = statement.where(
                PlatformCapabilityRecord.capability_type == capability_type
            )
        records = self.session.scalars(statement).all()
        capabilities = (self._to_domain(record) for record in records)
        return tuple(
            capability
            for capability in capabilities
            if capability.is_allowed(principal)
        )

    def get_available(
        self,
        code: str,
        *,
        principal: CapabilityPrincipal | None = None,
    ) -> PlatformCapability | None:
        record = self.session.scalar(
            select(PlatformCapabilityRecord)
            .where(PlatformCapabilityRecord.code == code)
            .where(PlatformCapabilityRecord.enabled.is_(True))
        )
        if record is None:
            return None
        capability = self._to_domain(record)
        return capability if capability.is_allowed(principal) else None

    @staticmethod
    def _to_domain(record: PlatformCapabilityRecord) -> PlatformCapability:
        return PlatformCapability(
            id=record.id,
            code=record.code,
            capability_type=record.capability_type,  # type: ignore[arg-type]
            description=record.description,
            input_schema=dict(record.input_schema or {}),
            output_schema=dict(record.output_schema or {}),
            required_fields=tuple(record.required_fields or ()),
            confirmation_policy=record.confirmation_policy,  # type: ignore[arg-type]
            permission=tuple(record.permission or ()),
            enabled=record.enabled,
            timeout_seconds=record.timeout_seconds,
            error_boundary=record.error_boundary,
            dispatch_key=record.dispatch_key,
            retrieval_metadata=dict(record.retrieval_metadata or {}),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
