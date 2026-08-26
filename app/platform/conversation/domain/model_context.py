from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.conversation.domain.message import Message, MessageRole


def _require_positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name}必须是正整数。")
    return value


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """选择模型上下文消息时使用的稳定策略。"""

    max_messages: int

    def __post_init__(self) -> None:
        _require_positive_int(self.max_messages, field_name="上下文消息数量上限")


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """模型上下文允许使用的最高成本单位数。"""

    max_cost: int

    def __post_init__(self) -> None:
        _require_positive_int(self.max_cost, field_name="上下文成本上限")


@dataclass(frozen=True, slots=True)
class ModelContextMessage:
    """从持久化 Message 映射出的模型中立上下文消息。"""

    source_message_id: UUID
    role: MessageRole
    content: str
    sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_message_id, UUID):
            raise ValueError("上下文消息来源标识必须是 UUID。")
        if not isinstance(self.role, MessageRole):
            raise ValueError("上下文消息角色无效。")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("上下文消息内容不能为空。")
        _require_positive_int(self.sequence, field_name="上下文消息顺序号")

    @classmethod
    def from_message(cls, message: Message) -> ModelContextMessage:
        return cls(
            source_message_id=message.id,
            role=message.role,
            content=message.content,
            sequence=message.sequence,
        )


@dataclass(frozen=True, slots=True)
class ModelContext:
    """在不绑定具体模型 SDK 的前提下传递给后续对话层的上下文。"""

    conversation_id: UUID
    messages: tuple[ModelContextMessage, ...]
    budget: ContextBudget
    used_cost: int
    omitted_message_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_id, UUID):
            raise ValueError("上下文会话标识必须是 UUID。")
        if not isinstance(self.budget, ContextBudget):
            raise ValueError("上下文预算无效。")
        if isinstance(self.used_cost, bool) or not isinstance(self.used_cost, int):
            raise ValueError("上下文已用成本必须是非负整数。")
        if self.used_cost < 0 or self.used_cost > self.budget.max_cost:
            raise ValueError("上下文已用成本超出预算。")
        if (
            isinstance(self.omitted_message_count, bool)
            or not isinstance(self.omitted_message_count, int)
            or self.omitted_message_count < 0
        ):
            raise ValueError("上下文省略消息数量必须是非负整数。")

        previous_sequence = 0
        for message in self.messages:
            if not isinstance(message, ModelContextMessage):
                raise ValueError("上下文消息类型无效。")
            if message.sequence <= previous_sequence:
                raise ValueError("上下文消息必须按顺序号严格递增。")
            previous_sequence = message.sequence
