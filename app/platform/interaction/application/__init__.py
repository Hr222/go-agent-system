"""平台交互应用服务。"""

from app.platform.interaction.application.agent_call_policy import (
    AgentCallPolicyCommand,
    AgentCallPolicyResult,
    AgentCallPolicyStatus,
    AgentCallPolicyValidator,
)
from app.platform.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatcher,
    AgentCallDispatchResult,
    AgentDispatchStatus,
)
from app.platform.interaction.application.attachment_resolution import (
    CapabilityAttachmentResolver,
)
from app.platform.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
    InMemoryCapabilityCandidateIndex,
)
from app.platform.interaction.application.catalog import PlatformCapabilityCatalog
from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
    InteractionStreamEvent,
    InteractionStreamPreparation,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.dispatch import (
    CapabilityDispatchBinding,
    CapabilityDispatchRegistry,
)
from app.platform.interaction.application.gateway import (
    ControlledDispatcher,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.platform.interaction.application.intent_recognition import (
    IntentRecognitionCommand,
    StructuredIntentRecognition,
)
from app.platform.interaction.ports.agent_runtime import AgentRuntimePort

__all__ = [
    "AgentCallPolicyCommand",
    "AgentCallPolicyResult",
    "AgentCallPolicyStatus",
    "AgentCallPolicyValidator",
    "CapabilityAttachmentResolver",
    "AgentCallDispatchCommand",
    "AgentCallDispatcher",
    "AgentCallDispatchResult",
    "AgentDispatchStatus",
    "AgentRuntimePort",
    "CapabilityDispatchBinding",
    "CapabilityDispatchRegistry",
    "CapabilityCandidateRetrieval",
    "ControlledDispatcher",
    "ExplicitCapabilityConfirmation",
    "GatewayConfirmationCommand",
    "GatewayRecognitionCommand",
    "GatewayResult",
    "InMemoryCapabilityCandidateIndex",
    "InMemoryPendingProposalStore",
    "IntentRecognitionCommand",
    "IntentInteractionGateway",
    "InteractionChatStreamApplication",
    "InteractionChatStreamCommand",
    "InteractionStreamEvent",
    "InteractionStreamPreparation",
    "PlatformCapabilityCatalog",
    "StructuredIntentRecognition",
]
