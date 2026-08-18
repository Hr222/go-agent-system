"""平台交互与能力目录模块。"""

from app.modules.interaction.application.candidate_retrieval import CapabilityCandidateRetrieval
from app.modules.interaction.application.catalog import PlatformCapabilityCatalog
from app.modules.interaction.application.chat_stream import InteractionChatStreamApplication
from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.gateway import IntentInteractionGateway
from app.modules.interaction.application.intent_recognition import StructuredIntentRecognition
from app.modules.interaction.domain.capability import (
    CapabilityPrincipal,
    CapabilityType,
    ConfirmationPolicy,
    PlatformCapability,
)

__all__ = [
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
]
