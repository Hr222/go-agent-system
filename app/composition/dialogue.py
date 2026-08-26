"""Dialogue Runtime 的 Composition Root。"""

from sqlalchemy.orm import Session

from app.composition.conversation import (
    build_conversation_context_builder,
    build_conversation_history_read_service,
    build_conversation_write_service,
)
from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationContextBuilder,
    ConversationHistoryReadService,
)
from app.platform.dialogue.application import (
    DEFAULT_DIALOGUE_CONTEXT_BUDGET,
    DEFAULT_DIALOGUE_CONTEXT_POLICY,
    BasicDialogueRuntime,
    StreamingConversationRuntime,
)
from app.platform.llm.contracts import ChatLlmPort, StreamingChatLlmPort


def build_basic_dialogue_runtime(
    session: Session,
    llm: ChatLlmPort,
    *,
    context_policy=DEFAULT_DIALOGUE_CONTEXT_POLICY,  # noqa: ANN001
    context_budget=DEFAULT_DIALOGUE_CONTEXT_BUDGET,  # noqa: ANN001
) -> BasicDialogueRuntime:
    """组装复用 Conversation 能力和既有 Chat LLM 的基础对话运行时。"""

    return BasicDialogueRuntime(
        conversation_writer=build_conversation_write_service(session),
        conversation_reader=build_conversation_history_read_service(session),
        context_builder=build_conversation_context_builder(),
        llm=llm,
        context_policy=context_policy,
        context_budget=context_budget,
    )


def build_streaming_conversation_runtime(
    session: Session,
    streaming_llm: StreamingChatLlmPort,
    conversation_access: ConversationAccessService,
    *,
    conversation_reader: ConversationHistoryReadService | None = None,
    context_builder: ConversationContextBuilder | None = None,
) -> StreamingConversationRuntime:
    """组装带 Conversation 历史上下文的流式 Dialogue 运行时。"""

    return StreamingConversationRuntime(
        conversation_access=conversation_access,
        conversation_writer=build_conversation_write_service(session),
        conversation_reader=(
            conversation_reader or build_conversation_history_read_service(session)
        ),
        context_builder=context_builder or build_conversation_context_builder(),
        llm=streaming_llm,
    )
