from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.platform.attachment.ports.storage_port import AttachmentStoragePort
from app.platform.security.domain.principal import RequestPrincipal

if TYPE_CHECKING:
    from app.platform.interaction.application.agent_dispatch import AgentCallDispatcher


@dataclass(frozen=True, slots=True)
class McpDispatchScope:
    """一次 MCP 调用使用的短生命周期分发依赖。"""

    dispatcher: AgentCallDispatcher
    attachment_storage: AttachmentStoragePort
    principal: RequestPrincipal


__all__ = ["McpDispatchScope"]
