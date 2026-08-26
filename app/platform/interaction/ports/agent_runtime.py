"""结构化 Agent 调用分发所需的运行时端口。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class AgentRuntimePort(Protocol):
    """执行已授权单个 Agent 调用的最小运行时边界。"""

    def execute(
        self,
        *,
        capability_code: str,
        dispatch_key: str,
        inputs: dict[str, object],
        permissions: Iterable[str] = (),
    ) -> object: ...


__all__ = ["AgentRuntimePort"]
