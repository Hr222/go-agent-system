from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from uuid import UUID

from app.modules.conversation.application import (
    ConversationContextBuilder,
    ConversationHistoryReadService,
    ConversationWriteService,
)
from app.modules.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Message,
    MessageRole,
    ModelContext,
    ModelContextMessage,
)
from app.modules.conversation.ports import MAX_HISTORY_PAGE_SIZE
from app.modules.llm.contracts import (
    ChatLlmMessage,
    ChatLlmMessageRole,
    ChatLlmPort,
    ChatLlmRequest,
)

DEFAULT_DIALOGUE_SYSTEM_PROMPT = (
    "你是一个通用中文助手。请结合已提供的对话历史，直接、清晰地回答当前用户消息。"
)
DEFAULT_DIALOGUE_PROMPT_VERSION = "dialogue-basic-chat-v1"
DEFAULT_DIALOGUE_CONTEXT_POLICY = ContextPolicy(max_messages=20)
DEFAULT_DIALOGUE_CONTEXT_BUDGET = ContextBudget(max_cost=12_000)


@dataclass(frozen=True, slots=True)
class DialogueCommand:
    conversation_id: UUID
    message: str


@dataclass(frozen=True, slots=True)
class DialogueResult:
    conversation_id: UUID
    user_message: Message
    assistant_message: Message
    context: ModelContext
    model: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class BasicDialogueRuntime:
    """编排单个已持久化 Conversation 的同步文本对话轮次。"""

    def __init__(
        self,
        *,
        conversation_writer: ConversationWriteService,
        conversation_reader: ConversationHistoryReadService,
        context_builder: ConversationContextBuilder,
        llm: ChatLlmPort,
        context_policy: ContextPolicy = DEFAULT_DIALOGUE_CONTEXT_POLICY,
        context_budget: ContextBudget = DEFAULT_DIALOGUE_CONTEXT_BUDGET,
        system_prompt: str = DEFAULT_DIALOGUE_SYSTEM_PROMPT,
        prompt_version: str = DEFAULT_DIALOGUE_PROMPT_VERSION,
    ) -> None:
        if not isinstance(context_policy, ContextPolicy):
            raise ValueError("对话上下文策略无效。")
        if not isinstance(context_budget, ContextBudget):
            raise ValueError("对话上下文预算无效。")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("对话系统提示不能为空。")
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            raise ValueError("对话提示版本不能为空。")

        self.conversation_writer = conversation_writer
        self.conversation_reader = conversation_reader
        self.context_builder = context_builder
        self.llm = llm
        self.context_policy = context_policy
        self.context_budget = context_budget
        self.system_prompt = system_prompt
        self.prompt_version = prompt_version

    def execute(self, command: DialogueCommand) -> DialogueResult:
        conversation_id, content = self._validate_command(command)
        user_message = self.conversation_writer.append_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
        )
        context = self.context_builder.build(
            conversation_id=conversation_id,
            messages=self._load_recent_messages(conversation_id),
            policy=self.context_policy,
            budget=self.context_budget,
        )
        llm_result = self.llm.invoke(
            self._build_llm_request(context=context, current_user_message=user_message)
        )
        answer = llm_result.content.strip()
        if not answer:
            raise RuntimeError("LLM 返回了空响应。")

        assistant_message = self.conversation_writer.append_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer,
        )
        return DialogueResult(
            conversation_id=conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
            context=context,
            model=llm_result.model,
            prompt_version=llm_result.prompt_version,
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
            total_tokens=llm_result.total_tokens,
        )

    def _validate_command(self, command: DialogueCommand) -> tuple[UUID, str]:
        if not isinstance(command, DialogueCommand):
            raise ValueError("对话命令无效。")
        if not isinstance(command.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        if not isinstance(command.message, str) or not command.message.strip():
            raise ValueError("消息内容不能为空。")
        return command.conversation_id, command.message.strip()

    def _load_recent_messages(self, conversation_id: UUID) -> tuple[Message, ...]:
        recent_messages: deque[Message] = deque(maxlen=self.context_policy.max_messages)
        after_sequence: int | None = None

        while True:
            page = self.conversation_reader.read_history(
                conversation_id=conversation_id,
                limit=MAX_HISTORY_PAGE_SIZE,
                after_sequence=after_sequence,
            )
            recent_messages.extend(page.messages)
            if not page.has_more:
                return tuple(recent_messages)
            if page.next_after_sequence is None:
                raise RuntimeError("历史分页缺少下一游标。")
            if after_sequence is not None and page.next_after_sequence <= after_sequence:
                raise RuntimeError("历史分页游标未前进。")
            after_sequence = page.next_after_sequence

    def _build_llm_request(
        self,
        *,
        context: ModelContext,
        current_user_message: Message,
    ) -> ChatLlmRequest:
        if not context.messages:
            raise RuntimeError("上下文未包含当前用户消息。")
        current_context_message = context.messages[-1]
        if (
            current_context_message.source_message_id != current_user_message.id
            or current_context_message.role is not MessageRole.USER
        ):
            raise RuntimeError("上下文未包含当前用户消息。")

        return ChatLlmRequest(
            system_prompt=self.system_prompt,
            user_prompt=current_user_message.content,
            prompt_version=self.prompt_version,
            history_messages=tuple(
                self._to_llm_history_message(message)
                for message in context.messages[:-1]
            ),
        )

    @staticmethod
    def _to_llm_history_message(message: ModelContextMessage) -> ChatLlmMessage:
        return ChatLlmMessage(
            role=ChatLlmMessageRole(message.role.value),
            content=message.content,
        )
