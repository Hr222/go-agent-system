"""平台能力目录领域契约。"""

from app.modules.interaction.domain.agent_call import (
    AgentCallError,
    AgentCallResult,
    StructuredAgentCall,
)
from app.modules.interaction.domain.candidate import (
    CapabilityCandidate,
    CapabilityCandidateIndexEntry,
    CapabilityCandidateRetrievalResult,
    CapabilityIndexBuildResult,
)
from app.modules.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    ConfirmationPolicy,
    PlatformCapability,
    validate_dispatch_key,
)
from app.modules.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
    ConfirmationResult,
)
from app.modules.interaction.domain.intent import (
    InputValidationResult,
    IntentAssessment,
    IntentAssessmentStatus,
    validate_capability_inputs,
)

__all__ = [
    "AgentCallError",
    "AgentCallResult",
    "CapabilityPrincipal",
    "CapabilityCandidate",
    "CapabilityCandidateIndexEntry",
    "CapabilityCandidateRetrievalResult",
    "CapabilityIndexBuildResult",
    "ApprovedCapabilityDispatch",
    "ConfirmationProposal",
    "ConfirmationResult",
    "InputValidationResult",
    "IntentAssessment",
    "IntentAssessmentStatus",
    "validate_capability_inputs",
    "CapabilityType",
    "ConfirmationPolicy",
    "PlatformCapability",
    "StructuredAgentCall",
    "validate_dispatch_key",
]
