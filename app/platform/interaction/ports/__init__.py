"""平台交互端口。"""

from app.platform.interaction.ports.agent_runtime import AgentRuntimePort
from app.platform.interaction.ports.attachment_resolver import CapabilityAttachmentResolverPort
from app.platform.interaction.ports.capability_catalog import (
    CapabilityCatalogPort,
    CapabilityCatalogRepositoryPort,
)
from app.platform.interaction.ports.proposal_store import PendingProposalStorePort

__all__ = [
    "CapabilityCatalogPort",
    "CapabilityCatalogRepositoryPort",
    "AgentRuntimePort",
    "CapabilityAttachmentResolverPort",
    "PendingProposalStorePort",
]
