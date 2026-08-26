from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.conversation.application.access_service import (
    ConversationAccessService,
    ConversationResolveQuery,
)
from app.platform.conversation.application.write_service import ConversationWriteService
from app.platform.conversation.domain import MAX_TOPIC_SUMMARY_LENGTH, Conversation
from app.platform.security.domain.principal import RequestPrincipal


@dataclass(frozen=True, slots=True)
class ConversationTopicSummaryUpdateCommand:
    principal: RequestPrincipal
    conversation_id: UUID
    topic_summary: str | None


class ConversationTopicSummaryUpdateService:
    """在当前主体范围内修改或清除 Conversation 话题概括。"""

    def __init__(
        self,
        *,
        access: ConversationAccessService,
        writer: ConversationWriteService,
    ) -> None:
        self._access = access
        self._writer = writer

    def update(self, command: ConversationTopicSummaryUpdateCommand) -> Conversation:
        if not isinstance(command, ConversationTopicSummaryUpdateCommand):
            raise ValueError("话题概括更新命令无效。")
        if not isinstance(command.conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        normalized = command.topic_summary.strip() if command.topic_summary is not None else None
        if normalized is not None and (
            not normalized
            or "\n" in normalized
            or "\r" in normalized
            or len(normalized) > MAX_TOPIC_SUMMARY_LENGTH
        ):
            raise ValueError("话题概括必须是单行且不超过 80 个字符。")
        self._access.resolve(
            ConversationResolveQuery(
                principal=command.principal,
                conversation_id=command.conversation_id,
            )
        )
        return self._writer.update_topic_summary(
            conversation_id=command.conversation_id,
            topic_summary=normalized,
        )


__all__ = [
    "ConversationTopicSummaryUpdateCommand",
    "ConversationTopicSummaryUpdateService",
]
