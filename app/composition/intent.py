"""Composition root for bounded intent recognition and confirmation."""

from collections.abc import AsyncIterator
from typing import Protocol

from app.platform.attachment.ports.read_port import AttachmentReadPort
from app.platform.dialogue.application import (
    DialogueAgentContinuationService,
    DialogueAgentInvocationService,
    InMemoryPendingAgentInvocationStore,
)
from app.platform.interaction.application.attachment_resolution import (
    CapabilityAttachmentResolver,
)
from app.platform.interaction.application.candidate_retrieval import (
    CapabilityCandidateRetrieval,
)
from app.platform.interaction.application.chat_stream import (
    InteractionChatStreamApplication,
)
from app.platform.interaction.application.confirmation import ExplicitCapabilityConfirmation
from app.platform.interaction.application.gateway import (
    ControlledDispatcher,
    IntentInteractionGateway,
)
from app.platform.interaction.application.intent_recognition import StructuredIntentRecognition
from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.interaction.ports.proposal_store import PendingProposalStorePort
from app.platform.llm.contracts import StructuredLlmPort


class StreamingRuntime(Protocol):
    async def execute(self, command: object) -> AsyncIterator[object]: ...


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
    attachment_reader: AttachmentReadPort,
) -> IntentInteractionGateway:
    return IntentInteractionGateway(
        candidate_retrieval=candidate_retrieval,
        intent_recognition=intent_recognition,
        confirmation=confirmation,
        proposal_store=proposal_store,
        dispatcher=dispatcher,
        attachment_resolver=CapabilityAttachmentResolver(attachment_reader),
    )


def build_interaction_chat_stream_application(
    gateway: IntentInteractionGateway,
    streaming_conversation: StreamingRuntime,
    dialogue_agent_invocation: DialogueAgentInvocationService | None = None,
    dialogue_agent_continuation: DialogueAgentContinuationService | None = None,
    pending_agent_invocations: InMemoryPendingAgentInvocationStore | None = None,
) -> InteractionChatStreamApplication:
    return InteractionChatStreamApplication(
        gateway,
        streaming_conversation,
        dialogue_agent_invocation=dialogue_agent_invocation,
        dialogue_agent_continuation=dialogue_agent_continuation,
        pending_agent_invocations=pending_agent_invocations,
    )
