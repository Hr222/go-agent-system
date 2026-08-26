"""平台交互与能力目录模块。"""

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
from app.platform.interaction.application.candidate_retrieval import CapabilityCandidateRetrieval
from app.platform.interaction.application.catalog import PlatformCapabilityCatalog
from app.platform.interaction.application.chat_stream import InteractionChatStreamApplication
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.gateway import IntentInteractionGateway
from app.platform.interaction.application.intent_recognition import StructuredIntentRecognition
from app.platform.interaction.domain.agent_call import (
    AgentCallError,
    AgentCallResult,
    StructuredAgentCall,
)
from app.platform.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    ConfirmationPolicy,
    PlatformCapability,
)
from app.platform.interaction.ports.agent_runtime import AgentRuntimePort

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
    "AgentCallError",
    "AgentCallResult",
    "CapabilityPrincipal",
    "CapabilityType",
    "ConfirmationPolicy",
    "PlatformCapability",
    "PlatformCapabilityCatalog",
    "CapabilityCandidateRetrieval",
    "ExplicitCapabilityConfirmation",
    "IntentInteractionGateway",
    "InteractionChatStreamApplication",
    "StructuredIntentRecognition",
    "StructuredAgentCall",
]
