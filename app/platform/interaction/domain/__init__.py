"""平台能力目录领域契约。"""

from app.platform.interaction.domain.agent_call import (
    AgentCallError,
    AgentCallResult,
    StructuredAgentCall,
)
from app.platform.interaction.domain.attachment import (
    AttachmentFieldDeclaration,
    AttachmentResolutionResult,
    ResolvedAttachment,
)
from app.platform.interaction.domain.candidate import (
    CapabilityCandidate,
    CapabilityCandidateIndexEntry,
    CapabilityCandidateRetrievalResult,
    CapabilityIndexBuildResult,
)
from app.platform.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    ConfirmationPolicy,
    PlatformCapability,
    validate_dispatch_key,
)
from app.platform.interaction.domain.confirmation import (
    ApprovedCapabilityDispatch,
    ConfirmationProposal,
    ConfirmationResult,
)
from app.platform.interaction.domain.intent import (
    InputValidationResult,
    IntentAssessment,
    IntentAssessmentStatus,
    validate_capability_inputs,
)

__all__ = [
    "AgentCallError",
    "AgentCallResult",
    "AttachmentFieldDeclaration",
    "AttachmentResolutionResult",
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
    "ResolvedAttachment",
    "StructuredAgentCall",
    "validate_dispatch_key",
]
