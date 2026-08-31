from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationContextBuilder,
    ConversationCreateCommand,
    ConversationHistoryReadService,
    ConversationRecentMessageReadService,
    ConversationResolveQuery,
    ConversationWriteService,
)
from app.platform.conversation.domain import (
    ContextBudget,
    ContextPolicy,
    Conversation,
    Message,
    MessageRole,
    ModelContext,
    ModelContextMessage,
)
from app.platform.conversation.errors import ConversationAccessDeniedError
from app.platform.conversation.ports import ConversationRecentMessageWindow
from app.platform.dialogue.application.conversation_turn_coordinator import (
    ConversationTurnCoordinator,
    ConversationTurnLease,
)
from app.platform.llm.contracts import (
    ChatLlmMessage,
    ChatLlmMessageRole,
    ChatLlmRequest,
    ChatLlmStreamChunk,
    StreamingChatLlmPort,
)
from app.platform.security.domain.principal import RequestPrincipal

StreamingConversationEventKind = Literal["started", "delta", "completed"]

DEFAULT_STREAMING_CONVERSATION_SYSTEM_PROMPT = (
    "你是一个通用中文助手。请结合已提供的对话历史，直接、清晰地回答当前用户消息。"
)
DEFAULT_STREAMING_CONVERSATION_PROMPT_VERSION = "dialogue-streaming-chat-v1"
DEFAULT_STREAMING_CONTEXT_POLICY = ContextPolicy(max_messages=20)
DEFAULT_STREAMING_CONTEXT_BUDGET = ContextBudget(max_cost=12_000)


class StreamingConversationPersistenceError(RuntimeError):
    """Conversation 创建或消息写入失败，供协议边界做安全错误映射。"""


@dataclass(frozen=True, slots=True)
class StreamingConversationCommand:
    """启动一轮使用同一 Conversation 历史上下文的流式对话。"""

    principal: RequestPrincipal
    message: str
    conversation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class StreamingConversationResult:
    """一轮完整成功的流式 Conversation 结果。"""

    conversation_id: UUID
    user_message: Message
    assistant_message: Message
    model: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True, slots=True)
class StreamingConversationEvent:
    """流式 Conversation 的应用层事件，不携带 HTTP/SSE 语义。"""

    kind: StreamingConversationEventKind
    conversation_id: UUID
    chunk: ChatLlmStreamChunk | None = None
    result: StreamingConversationResult | None = None


class _LeaseReleasingStream(AsyncIterator[StreamingConversationEvent]):
    """Close an inner Conversation stream and release its turn lease once."""

    def __init__(
        self,
        stream: AsyncIterator[StreamingConversationEvent],
        lease: ConversationTurnLease,
    ) -> None:
        self._stream = stream
        self._lease = lease
        self._closed = False

    def __aiter__(self) -> _LeaseReleasingStream:
        return self

    async def __anext__(self) -> StreamingConversationEvent:
        if self._closed:
            raise StopAsyncIteration
        try:
            return await anext(self._stream)
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await _close_stream(self._stream)
        finally:
            self._lease.release()


class StreamingConversationRuntime:
    """持久化普通流式对话事实，并在完整成功后提交 assistant 消息。"""

    def __init__(
        self,
        *,
        conversation_access: ConversationAccessService,
        conversation_writer: ConversationWriteService,
        conversation_reader: ConversationRecentMessageReadService,
        context_builder: ConversationContextBuilder,
        llm: StreamingChatLlmPort,
        conversation_turn_coordinator: ConversationTurnCoordinator,
        context_policy: ContextPolicy = DEFAULT_STREAMING_CONTEXT_POLICY,
        context_budget: ContextBudget = DEFAULT_STREAMING_CONTEXT_BUDGET,
        system_prompt: str = DEFAULT_STREAMING_CONVERSATION_SYSTEM_PROMPT,
        prompt_version: str = DEFAULT_STREAMING_CONVERSATION_PROMPT_VERSION,
    ) -> None:
        if not isinstance(context_policy, ContextPolicy):
            raise ValueError("对话上下文策略无效。")
        if not isinstance(context_budget, ContextBudget):
            raise ValueError("对话上下文预算无效。")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("对话系统提示不能为空。")
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            raise ValueError("对话提示版本不能为空。")

        self._conversation_access = conversation_access
        self._conversation_writer = conversation_writer
        self._conversation_reader = conversation_reader
        self._context_builder = context_builder
        self._llm = llm
        self._conversation_turn_coordinator = conversation_turn_coordinator
        self._context_policy = context_policy
        self._context_budget = context_budget
        self._system_prompt = system_prompt
        self._prompt_version = prompt_version

    async def execute(
        self,
        command: StreamingConversationCommand,
    ) -> AsyncIterator[StreamingConversationEvent]:
        conversation = self._resolve_conversation(command)
        lease = await self._conversation_turn_coordinator.acquire(conversation.id)
        try:
            user_message = self._append_user_message(conversation, command.message)
            context = self._context_builder.build(
                conversation_id=conversation.id,
                messages=self._read_recent_messages(
                    conversation.id,
                    user_message.sequence,
                ),
                policy=self._context_policy,
                budget=self._context_budget,
            )
            request = self._build_llm_request(
                context=context,
                current_user_message=user_message,
            )
            return _LeaseReleasingStream(
                self._stream_turn(
                    conversation=conversation,
                    user_message=user_message,
                    request=request,
                ),
                lease,
            )
        except BaseException:
            lease.release()
            raise

    def _resolve_conversation(
        self,
        command: StreamingConversationCommand,
    ) -> Conversation:
        if not isinstance(command, StreamingConversationCommand):
            raise ValueError("流式 Conversation 命令无效。")
        if not isinstance(command.principal, RequestPrincipal):
            raise ValueError("请求主体无效。")
        if not isinstance(command.message, str) or not command.message.strip():
            raise ValueError("消息内容不能为空。")
        if command.conversation_id is not None and not isinstance(command.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")

        try:
            return (
                self._conversation_access.create(
                    ConversationCreateCommand(principal=command.principal)
                )
                if command.conversation_id is None
                else self._conversation_access.resolve(
                    ConversationResolveQuery(
                        principal=command.principal,
                        conversation_id=command.conversation_id,
                    )
                )
            )
        except Exception as error:
            if isinstance(error, ConversationAccessDeniedError):
                raise
            raise StreamingConversationPersistenceError("会话消息暂时无法保存。") from error

    def _append_user_message(
        self,
        conversation: Conversation,
        message: str,
    ) -> Message:
        try:
            return self._conversation_writer.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=message.strip(),
            )
        except Exception as error:
            raise StreamingConversationPersistenceError("会话消息暂时无法保存。") from error

    def _stream_turn(
        self,
        *,
        conversation: Conversation,
        user_message: Message,
        request: ChatLlmRequest,
    ) -> AsyncIterator[StreamingConversationEvent]:
        return self._stream_turn_generator(
            conversation=conversation,
            user_message=user_message,
            request=request,
        )

    async def _stream_turn_generator(
        self,
        *,
        conversation: Conversation,
        user_message: Message,
        request: ChatLlmRequest,
    ) -> AsyncIterator[StreamingConversationEvent]:
        stream: AsyncIterator[ChatLlmStreamChunk] | None = None
        chunks: list[ChatLlmStreamChunk] = []
        try:
            yield StreamingConversationEvent(
                kind="started",
                conversation_id=conversation.id,
            )
            stream = self._llm.stream(
                request=request,
            )
            async for chunk in stream:
                chunks.append(chunk)
                yield StreamingConversationEvent(
                    kind="delta",
                    conversation_id=conversation.id,
                    chunk=chunk,
                )

            answer = "".join(chunk.content for chunk in chunks).strip()
            if not answer:
                raise RuntimeError("LLM 返回了空响应。")

            latest = chunks[-1] if chunks else None
            try:
                assistant_message = self._conversation_writer.append_message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=answer,
                )
            except Exception as error:
                raise StreamingConversationPersistenceError(
                    str(error) or "助手消息写入失败。"
                ) from error
            result = StreamingConversationResult(
                conversation_id=conversation.id,
                user_message=user_message,
                assistant_message=assistant_message,
                model=latest.model if latest is not None else None,
                prompt_version=(
                    latest.prompt_version if latest is not None else self._prompt_version
                ),
                input_tokens=latest.input_tokens if latest is not None else None,
                output_tokens=latest.output_tokens if latest is not None else None,
                total_tokens=latest.total_tokens if latest is not None else None,
            )
            yield StreamingConversationEvent(
                kind="completed",
                conversation_id=conversation.id,
                result=result,
            )
        finally:
            if stream is not None:
                await _close_stream(stream)

    def _read_recent_messages(
        self,
        conversation_id: UUID,
        through_sequence: int,
    ) -> tuple[Message, ...]:
        try:
            window: ConversationRecentMessageWindow = self._conversation_reader.read_recent_messages(
                conversation_id=conversation_id,
                through_sequence=through_sequence,
                limit=self._context_policy.max_messages,
            )
            return window.messages
        except Exception as error:
            raise StreamingConversationPersistenceError(
                str(error) or "会话历史暂时无法读取。"
            ) from error

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
            system_prompt=self._system_prompt,
            user_prompt=current_user_message.content,
            prompt_version=self._prompt_version,
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


async def _close_stream(stream: AsyncIterator[ChatLlmStreamChunk]) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None:
        await close()


__all__ = [
    "StreamingConversationCommand",
    "StreamingConversationEvent",
    "StreamingConversationEventKind",
    "StreamingConversationPersistenceError",
    "StreamingConversationResult",
    "StreamingConversationRuntime",
    "DEFAULT_STREAMING_CONVERSATION_PROMPT_VERSION",
    "DEFAULT_STREAMING_CONVERSATION_SYSTEM_PROMPT",
    "DEFAULT_STREAMING_CONTEXT_BUDGET",
    "DEFAULT_STREAMING_CONTEXT_POLICY",
]

