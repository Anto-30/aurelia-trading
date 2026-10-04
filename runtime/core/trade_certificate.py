from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .economics import TradeEconomics
from .events import sha256
from .models import AuthorizationContext, OrderIntent, utc_now


@dataclass(frozen=True)
class TradeCertificate:
    certificate_id: str
    intent_id: str
    decision_id: str
    strategy_id: str
    strategy_version: str
    strategy_hash: str
    symbol: str
    direction: str
    probability: float
    expected_value: float
    stake: float
    account_loginid: str
    account_currency: str
    account_environment: str
    market_snapshot_hash: str
    proposal_id: str
    authorization_id: str
    config_hash: str
    idempotency_key: str
    fence_generation: int
    fence_owner: str
    issued_at: Any

    @classmethod
    def from_authorization(
        cls,
        *,
        intent: OrderIntent,
        authorization: AuthorizationContext,
        fence_token: Any,
    ) -> "TradeCertificate":
        decision = authorization.decision
        if decision.average_win is None or decision.average_loss is None:
            raise ValueError("TRADE_CERTIFICATE_EXPECTED_VALUE_INPUTS_MISSING")
        expected_value = TradeEconomics(
            probability=decision.probability,
            average_win=float(decision.average_win),
            average_loss=float(decision.average_loss),
            execution_cost=float(decision.execution_cost),
            slippage_cost=float(decision.slippage_cost),
            quote_cost=float(decision.quote_cost),
        ).expected_value
        return cls(
            certificate_id=f"trade-cert:{intent.intent_id}",
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            strategy_id=decision.strategy_id,
            strategy_version=decision.strategy_version,
            strategy_hash=intent.strategy_hash,
            symbol=intent.symbol,
            direction=intent.direction,
            probability=decision.probability,
            expected_value=expected_value,
            stake=intent.stake,
            account_loginid=intent.account.loginid,
            account_currency=intent.account.currency,
            account_environment=intent.account.environment,
            market_snapshot_hash=decision.market_snapshot_hash,
            proposal_id=str(intent.proposal_id),
            authorization_id=authorization.authorization_id,
            config_hash=intent.config_hash,
            idempotency_key=intent.intent_id,
            fence_generation=int(fence_token.generation),
            fence_owner=str(fence_token.owner),
            issued_at=utc_now(),
        )

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issued_at"] = self.issued_at.isoformat()
        payload["certificate_hash"] = sha256(payload)
        return payload
