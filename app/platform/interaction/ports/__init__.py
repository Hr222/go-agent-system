"""平台交互端口。"""

from app.platform.interaction.ports.agent_execution import (
    AgentExecutionCommand,
    AgentExecutionOutcome,
    AgentExecutionStatus,
    AgentExecutionStrategyPort,
)
from app.platform.interaction.ports.agent_runtime import AgentRuntimePort
from app.platform.interaction.ports.agent_task_bridge import (
    AgentTaskInputSnapshot,
    AgentTaskInputSnapshotPort,
    AgentTaskProfile,
    AgentTaskProfileRegistryPort,
    AgentTaskRoute,
    AgentTaskSubmissionPort,
)
from app.platform.interaction.ports.attachment_resolver import CapabilityAttachmentResolverPort
from app.platform.interaction.ports.capability_catalog import (
    CapabilityCatalogPort,
    CapabilityCatalogRepositoryPort,
)
from app.platform.interaction.ports.chat_preparation import (
    InteractionChatPreparationPort,
    InteractionChatPreparationWorkerFactoryPort,
    InteractionChatPreparationWorkerPort,
)
from app.platform.interaction.ports.mcp_dispatch import McpDispatchScope
from app.platform.interaction.ports.proposal_store import PendingProposalStorePort

__all__ = [
    "CapabilityCatalogPort",
    "CapabilityCatalogRepositoryPort",
    "InteractionChatPreparationPort",
    "InteractionChatPreparationWorkerFactoryPort",
    "InteractionChatPreparationWorkerPort",
    "AgentRuntimePort",
    "AgentTaskInputSnapshot",
    "AgentTaskInputSnapshotPort",
    "AgentTaskProfile",
    "AgentTaskProfileRegistryPort",
    "AgentTaskRoute",
    "AgentTaskSubmissionPort",
    "AgentExecutionCommand",
    "AgentExecutionOutcome",
    "AgentExecutionStatus",
    "AgentExecutionStrategyPort",
    "CapabilityAttachmentResolverPort",
    "McpDispatchScope",
    "PendingProposalStorePort",
]
