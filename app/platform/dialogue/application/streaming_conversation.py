from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.platform.conversation.application import (
    ConversationAccessService,
    ConversationCreateCommand,
    ConversationResolveQuery,
    ConversationWriteService,
)
from app.platform.conversation.domain import Conversation, Message, MessageRole
from app.platform.conversation.errors import ConversationAccessDeniedError
from app.platform.llm.application.chat import (
    DEFAULT_CHAT_PROMPT_VERSION,
    DEFAULT_CHAT_SYSTEM_PROMPT,
)
from app.platform.llm.contracts import (
    ChatLlmRequest,
    ChatLlmStreamChunk,
    StreamingChatLlmPort,
)
from app.platform.security.domain.principal import RequestPrincipal

StreamingConversationEventKind = Literal["started", "delta", "completed"]


class StreamingConversationPersistenceError(RuntimeError):
    """Conversation 创建或消息写入失败，供协议边界做安全错误映射。"""


@dataclass(frozen=True, slots=True)
class StreamingConversationCommand:
    """启动一轮不读取历史上下文的流式 Conversation 对话。"""

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


class StreamingConversationRuntime:
    """持久化普通流式对话事实，并在完整成功后提交 assistant 消息。"""

    def __init__(
        self,
        *,
        conversation_access: ConversationAccessService,
        conversation_writer: ConversationWriteService,
        llm: StreamingChatLlmPort,
        system_prompt: str = DEFAULT_CHAT_SYSTEM_PROMPT,
        prompt_version: str = DEFAULT_CHAT_PROMPT_VERSION,
    ) -> None:
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("对话系统提示不能为空。")
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            raise ValueError("对话提示版本不能为空。")

        self._conversation_access = conversation_access
        self._conversation_writer = conversation_writer
        self._llm = llm
        self._system_prompt = system_prompt
        self._prompt_version = prompt_version

    async def execute(
        self,
        command: StreamingConversationCommand,
    ) -> AsyncIterator[StreamingConversationEvent]:
        conversation, user_message = self._prepare_turn(command)
        return self._stream_turn(conversation=conversation, user_message=user_message)

    def _prepare_turn(
        self,
        command: StreamingConversationCommand,
    ) -> tuple[Conversation, Message]:
        if not isinstance(command, StreamingConversationCommand):
            raise ValueError("流式 Conversation 命令无效。")
        if not isinstance(command.principal, RequestPrincipal):
            raise ValueError("请求主体无效。")
        if not isinstance(command.message, str) or not command.message.strip():
            raise ValueError("消息内容不能为空。")
        if command.conversation_id is not None and not isinstance(command.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")

        try:
            conversation = (
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
            user_message = self._conversation_writer.append_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=command.message.strip(),
            )
        except Exception as error:
            if isinstance(error, ConversationAccessDeniedError):
                raise
            raise StreamingConversationPersistenceError("会话消息暂时无法保存。") from error
        return conversation, user_message

    def _stream_turn(
        self,
        *,
        conversation: Conversation,
        user_message: Message,
    ) -> AsyncIterator[StreamingConversationEvent]:
        return self._stream_turn_generator(
            conversation=conversation,
            user_message=user_message,
        )

    async def _stream_turn_generator(
        self,
        *,
        conversation: Conversation,
        user_message: Message,
    ) -> AsyncIterator[StreamingConversationEvent]:
        stream: AsyncIterator[ChatLlmStreamChunk] | None = None
        chunks: list[ChatLlmStreamChunk] = []
        try:
            yield StreamingConversationEvent(
                kind="started",
                conversation_id=conversation.id,
            )
            stream = self._llm.stream(
                request=ChatLlmRequest(
                    system_prompt=self._system_prompt,
                    user_prompt=user_message.content,
                    prompt_version=self._prompt_version,
                )
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
]
