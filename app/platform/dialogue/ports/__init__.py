"""Dialogue 能力依赖的稳定端口。"""

from app.platform.dialogue.ports.persistence import (
    StreamingConversationPersistencePort,
    StreamingConversationPersistenceWorkerFactoryPort,
    StreamingConversationPersistenceWorkerPort,
)

__all__ = [
    "StreamingConversationPersistencePort",
    "StreamingConversationPersistenceWorkerFactoryPort",
    "StreamingConversationPersistenceWorkerPort",
]
