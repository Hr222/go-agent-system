"""Composition root for bounded intent recognition and confirmation."""

from app.modules.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
)
from app.modules.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
)
from app.modules.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.modules.interaction.application.gateway import (
    ControlledDispatcher,
    IntentInteractionGateway,
)
from app.modules.interaction.application.intent_recognition import StructuredIntentRecognition
from app.modules.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.modules.interaction.ports.proposal_store import PendingProposalStorePort
from app.modules.llm.application.streaming_chat import StreamingChatApplication
from app.modules.llm.contracts import StructuredLlmPort


def build_structured_intent_recognition(
    candidate_retrieval: CapabilityCandidateRetrieval,
    capability_catalog: CapabilityCatalogPort,
    llm: StructuredLlmPort,
) -> StructuredIntentRecognition:
    return StructuredIntentRecognition(candidate_retrieval, capability_catalog, llm)


def build_explicit_capability_confirmation(
    capability_catalog: CapabilityCatalogPort,
) -> ExplicitCapabilityConfirmation:
    return ExplicitCapabilityConfirmation(capability_catalog)


def build_intent_interaction_gateway(
    *,
    candidate_retrieval: CapabilityCandidateRetrieval,
    intent_recognition: StructuredIntentRecognition,
    confirmation: ExplicitCapabilityConfirmation,
    proposal_store: PendingProposalStorePort,
    dispatcher: ControlledDispatcher,
) -> IntentInteractionGateway:
    return IntentInteractionGateway(
        candidate_retrieval=candidate_retrieval,
        intent_recognition=intent_recognition,
        confirmation=confirmation,
        proposal_store=proposal_store,
        dispatcher=dispatcher,
    )


def build_interaction_chat_stream_application(
    gateway: IntentInteractionGateway,
    streaming_chat: StreamingChatApplication,
) -> InteractionChatStreamApplication:
    return InteractionChatStreamApplication(gateway, streaming_chat)
