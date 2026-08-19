"""平台交互应用服务。"""

from app.modules.interaction.application.agent_call_policy import (
    AgentCallPolicyCommand,
    AgentCallPolicyResult,
    AgentCallPolicyStatus,
    AgentCallPolicyValidator,
)
from app.modules.interaction.application.agent_dispatch import (
    AgentCallDispatchCommand,
    AgentCallDispatcher,
    AgentCallDispatchResult,
    AgentDispatchStatus,
)
from app.modules.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
    InMemoryCapabilityCandidateIndex,
)
from app.modules.interaction.application.catalog import PlatformCapabilityCatalog
from app.modules.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
    InteractionChatStreamCommand,
    InteractionStreamEvent,
    InteractionStreamPreparation,
)
from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.dispatch import (
    CapabilityDispatchBinding,
    CapabilityDispatchRegistry,
)
from app.modules.interaction.application.gateway import (
    ControlledDispatcher,
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
    InMemoryPendingProposalStore,
    IntentInteractionGateway,
)
from app.modules.interaction.application.intent_recognition import (
    IntentRecognitionCommand,
    StructuredIntentRecognition,
)
from app.modules.interaction.ports.agent_runtime import AgentRuntimePort

__all__ = [
    "AgentCallPolicyCommand",
    "AgentCallPolicyResult",
    "AgentCallPolicyStatus",
    "AgentCallPolicyValidator",
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
