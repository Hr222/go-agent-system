from __future__ import annotations

import logging
from uuid import UUID

from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.conversation.application.topic_summary import normalize_topic_summary
from app.modules.conversation.ports import ConversationTopicSummaryGenerator
from app.modules.conversation.ports.write_port import ConversationWritePort

logger = logging.getLogger(__name__)


class ConversationWriteService:
    """创建会话并追加消息的最小应用服务。"""

    def __init__(
        self,
        write_port: ConversationWritePort,
        topic_summary_generator: ConversationTopicSummaryGenerator | None = None,
    ) -> None:
        self.write_port = write_port
        self.topic_summary_generator = topic_summary_generator

    def create_conversation(self, *, owner_subject: str) -> Conversation:
        """创建并持久化一个绑定可信主体的新会话。"""

        return self.write_port.save_conversation(Conversation(owner_subject=owner_subject))

    def update_topic_summary(
        self,
        *,
        conversation_id: UUID,
        topic_summary: str | None,
    ) -> Conversation:
        return self.write_port.update_topic_summary(
            conversation_id=conversation_id,
            topic_summary=topic_summary,
        )

    def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole | str,
        content: str,
    ) -> Message:
        """校验输入后，将顺序分配和持久化交给写入端口。"""

        if not isinstance(conversation_id, UUID):
            raise ValueError("会话标识必须是 UUID。")
        try:
            normalized_role = MessageRole(role)
        except (TypeError, ValueError) as error:
            raise ValueError("消息角色无效。") from error
        if not isinstance(content, str) or not content.strip():
            raise ValueError("消息内容不能为空。")

        message = self.write_port.append_message(
            conversation_id=conversation_id,
            role=normalized_role,
            content=content,
        )
        self.maybe_generate_topic_summary(conversation_id=conversation_id, message=message)
        return message

    def maybe_generate_topic_summary(self, *, conversation_id: UUID, message: Message) -> None:
        if (
            self.topic_summary_generator is None
            or message.role is not MessageRole.USER
            or message.sequence != 1
        ):
            return
        self._try_generate_topic_summary(conversation_id, message.content)

    def _try_generate_topic_summary(self, conversation_id: UUID, content: str) -> None:
        try:
            try:
                generated = self.topic_summary_generator.generate(content)
                candidate = normalize_topic_summary(generated)
            except Exception:
                logger.exception("会话话题概括生成器失败，使用首条消息回退。")
                candidate = None
            candidate = candidate or normalize_topic_summary(content)
            if candidate is None:
                return
            self.write_port.update_topic_summary_if_empty(
                conversation_id=conversation_id,
                topic_summary=candidate,
            )
        except Exception:
            logger.exception("会话话题概括生成失败，会话消息已保留。", extra={"conversation_id": str(conversation_id)})
