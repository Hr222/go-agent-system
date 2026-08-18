from __future__ import annotations

from typing import Protocol

from app.modules.interaction.domain.confirmation import ConfirmationProposal


class PendingProposalStorePort(Protocol):
    """保存短期确认提议；实现必须保证单次消费。"""

    def save(self, proposal: ConfirmationProposal, *, subject: str | None) -> None: ...

    def consume(
        self,
        proposal_id: str,
        *,
        subject: str | None,
    ) -> ConfirmationProposal | None: ...
