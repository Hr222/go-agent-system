"""Dialogue Runtime 应用用例。"""

from app.platform.dialogue.application.agent_continuation import (
    DEFAULT_CONTINUATION_CONTEXT_BUDGET,
    DEFAULT_CONTINUATION_CONTEXT_POLICY,
    DEFAULT_CONTINUATION_PROMPT_VERSION,
    DEFAULT_CONTINUATION_SYSTEM_PROMPT,
    DialogueAgentContinuationCommand,
    DialogueAgentContinuationResult,
    DialogueAgentContinuationService,
)
from app.platform.dialogue.application.agent_invocation import (
    DialogueAgentInvocationCommand,
    DialogueAgentInvocationResult,
    DialogueAgentInvocationService,
)
from app.platform.dialogue.application.agent_result_projection import AgentResultProjector
from app.platform.dialogue.application.basic_chat import (
    DEFAULT_DIALOGUE_CONTEXT_BUDGET,
    DEFAULT_DIALOGUE_CONTEXT_POLICY,
    DEFAULT_DIALOGUE_PROMPT_VERSION,
    DEFAULT_DIALOGUE_SYSTEM_PROMPT,
    BasicDialogueRuntime,
    DialogueCommand,
    DialogueResult,
)
from app.platform.dialogue.application.pending_invocation import (
    InMemoryPendingAgentInvocationStore,
    PendingAgentInvocation,
)
from app.platform.dialogue.application.streaming_conversation import (
    StreamingConversationCommand,
    StreamingConversationEvent,
    StreamingConversationEventKind,
    StreamingConversationPersistenceError,
    StreamingConversationResult,
    StreamingConversationRuntime,
)

__all__ = [
    "DEFAULT_DIALOGUE_CONTEXT_BUDGET",
    "DEFAULT_DIALOGUE_CONTEXT_POLICY",
    "DEFAULT_DIALOGUE_PROMPT_VERSION",
    "DEFAULT_DIALOGUE_SYSTEM_PROMPT",
    "BasicDialogueRuntime",
    "DialogueCommand",
    "DialogueResult",
    "AgentResultProjector",
    "DEFAULT_CONTINUATION_CONTEXT_BUDGET",
    "DEFAULT_CONTINUATION_CONTEXT_POLICY",
    "DEFAULT_CONTINUATION_PROMPT_VERSION",
    "DEFAULT_CONTINUATION_SYSTEM_PROMPT",
    "DialogueAgentContinuationCommand",
    "DialogueAgentContinuationResult",
    "DialogueAgentContinuationService",
    "DialogueAgentInvocationCommand",
    "DialogueAgentInvocationResult",
    "DialogueAgentInvocationService",
    "InMemoryPendingAgentInvocationStore",
    "PendingAgentInvocation",
    "StreamingConversationCommand",
    "StreamingConversationEvent",
    "StreamingConversationEventKind",
    "StreamingConversationPersistenceError",
    "StreamingConversationResult",
    "StreamingConversationRuntime",
]
