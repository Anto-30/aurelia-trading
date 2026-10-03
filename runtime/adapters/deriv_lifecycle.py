from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from runtime.core.models import BrokerOutcome


@dataclass(frozen=True)
class BrokerLifecycleRecord:
    intent_id: str
    proposal_id: str | None = None
    transaction_id: str | None = None
    contract_id: str | None = None
    outcome: BrokerOutcome = BrokerOutcome.UNKNOWN
    observed_at: datetime | None = None
    reconciled: bool = False

    def with_broker_acceptance(self, transaction_id: str | None, contract_id: str | None):
        return BrokerLifecycleRecord(
            intent_id=self.intent_id,
            proposal_id=self.proposal_id,
            transaction_id=transaction_id,
            contract_id=contract_id,
            outcome=BrokerOutcome.ACCEPTED,
            observed_at=datetime.now(timezone.utc),
            reconciled=False,
        )

    def settled(self):
        return BrokerLifecycleRecord(
            intent_id=self.intent_id,
            proposal_id=self.proposal_id,
            transaction_id=self.transaction_id,
            contract_id=self.contract_id,
            outcome=BrokerOutcome.SETTLED,
            observed_at=datetime.now(timezone.utc),
            reconciled=self.reconciled,
        )


async def monitor_contract(adapter, contract_id: str) -> AsyncIterator[dict[str, Any]]:
    '''Continuously query contract status until broker marks it closed.'''
    while True:
        status = await adapter.get_contract_status(contract_id)
        yield status
        is_sold = bool(status.get("is_sold"))
        status_value = str(status.get("status") or "").lower()
        if is_sold or status_value in {"sold", "closed", "won", "lost", "expired"}:
            return
