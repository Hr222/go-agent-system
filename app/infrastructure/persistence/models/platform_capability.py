from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    INTEGER,
    TIMESTAMP,
    CheckConstraint,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class PlatformCapabilityRecord(Base):
    """平台能力目录持久化实体。"""

    __tablename__ = "platform_capability"
    __table_args__ = (
        UniqueConstraint("code", name="uq_platform_capability_code"),
        CheckConstraint(
            "capability_type IN ('agent', 'chat', 'knowledge_qa', 'policy_decision')",
            name="chk_platform_capability_type",
        ),
        CheckConstraint(
            "confirmation_policy IN ('always', 'conditional', 'never')",
            name="chk_platform_capability_confirmation_policy",
        ),
        CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 3600",
            name="chk_platform_capability_timeout",
        ),
        CheckConstraint("btrim(code) <> ''", name="chk_platform_capability_code_not_blank"),
        CheckConstraint(
            "btrim(description) <> ''",
            name="chk_platform_capability_description_not_blank",
        ),
        CheckConstraint(
            "code ~ '^[a-z][a-z0-9]*([._-][a-z0-9]+)*$'",
            name="chk_platform_capability_code_format",
        ),
        CheckConstraint(
            "btrim(dispatch_key) <> ''",
            name="chk_platform_capability_dispatch_key_not_blank",
        ),
        CheckConstraint(
            "dispatch_key ~ '^[a-z][a-z0-9]*([._-][a-z0-9]+)*$'",
            name="chk_platform_capability_dispatch_key_format",
        ),
        CheckConstraint(
            "btrim(error_boundary) <> ''",
            name="chk_platform_capability_error_boundary_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    capability_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confirmation_policy: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="always",
    )
    permission: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(INTEGER, nullable=False, default=300)
    error_boundary: Mapped[str] = mapped_column(Text, nullable=False)
    dispatch_key: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
