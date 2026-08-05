from __future__ import annotations

from typing import Protocol

from app.modules.agent.tender.contracts import (
    TenderFillContentCommand,
    TenderFillContentResult,
)


class TenderFillContentPort(Protocol):
    """V2 公司资料填充能力的预留端口。"""

    def fill(self, command: TenderFillContentCommand) -> TenderFillContentResult: ...

