from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.platform.interaction.application.chat_stream import (
        InteractionChatStreamCommand,
        InteractionStreamPreparation,
    )


class InteractionChatPreparationWorkerPort(Protocol):
    """执行一次同步交互准备的短生命周期 Worker。"""

    def prepare(self, command: InteractionChatStreamCommand) -> InteractionStreamPreparation: ...

    def cancel_preparation(
        self,
        command: InteractionChatStreamCommand,
        preparation: InteractionStreamPreparation,
    ) -> None: ...

    def close(self) -> None: ...


class InteractionChatPreparationWorkerFactoryPort(Protocol):
    """创建不携带请求级资源的交互准备 Worker。"""

    def create(self) -> InteractionChatPreparationWorkerPort: ...


class InteractionChatPreparationPort(Protocol):
    """普通流式 Chat 使用的异步交互准备能力。"""

    async def prepare(
        self,
        command: InteractionChatStreamCommand,
    ) -> InteractionStreamPreparation: ...
