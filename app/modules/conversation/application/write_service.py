from __future__ import annotations

from uuid import UUID

from app.modules.conversation.domain import Conversation, Message, MessageRole
from app.modules.conversation.ports.write_port import ConversationWritePort


class ConversationWriteService:
    """创建会话并追加消息的最小应用服务。"""

    def __init__(self, write_port: ConversationWritePort) -> None:
        self.write_port = write_port

    def create_conversation(self, *, owner_subject: str) -> Conversation:
        """创建并持久化一个绑定可信主体的新会话。"""

        return self.write_port.save_conversation(Conversation(owner_subject=owner_subject))

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

        return self.write_port.append_message(
            conversation_id=conversation_id,
            role=normalized_role,
            content=content,
        )
