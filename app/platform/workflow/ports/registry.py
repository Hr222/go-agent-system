from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.platform.workflow.domain import WorkflowVersion


class WorkflowDefinitionRegistryPort(Protocol):
    """只读的服务端 Workflow Version 注册表。"""

    def get(self, workflow_code: str, version: str) -> WorkflowVersion | None: ...

    def validate(self) -> None: ...

    def validate_access(self, version: WorkflowVersion, permissions: Iterable[str]) -> None: ...
