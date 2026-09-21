"""Workflow 固定 Version 与受信任 Application 的 Composition。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.workflow_repository import (
    PostgresWorkflowRepository,
)
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.workflow.application import WorkflowApplication, WorkflowDefinitionRegistry
from app.platform.workflow.domain import (
    WorkflowNodeDefinition,
    WorkflowNodeType,
    WorkflowVersion,
)


def build_registered_workflow_versions(
    capability_catalog: CapabilityCatalogPort,
) -> WorkflowDefinitionRegistry:
    """当前只注册一个 Tender 能力样本；动态 Definition 不在此入口开放。"""

    tender = WorkflowVersion(
        workflow_code="tender-generation",
        version="v1",
        nodes=(
            WorkflowNodeDefinition(
                node_id="generate",
                node_type=WorkflowNodeType.CAPABILITY,
                capability_code="tender.generate_bid_skeleton",
                input_fields=("source_document",),
                output_fields=("analysis", "artifacts"),
                max_attempts=2,
            ),
        ),
    )
    return WorkflowDefinitionRegistry(
        (tender,),
        capability_catalog,
        validation_permissions=("agent:tender:execute",),
    )


def build_workflow_application(
    session: Session,
    capability_catalog: CapabilityCatalogPort,
    *,
    clock=None,  # noqa: ANN001
) -> WorkflowApplication:
    registry = build_registered_workflow_versions(capability_catalog)
    return WorkflowApplication(
        PostgresWorkflowRepository(session),
        registry,
        clock=clock or _utc_now,
    )


def _utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


__all__ = ["build_registered_workflow_versions", "build_workflow_application"]
