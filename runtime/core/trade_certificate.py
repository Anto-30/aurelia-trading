from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .events import sha256
from .models import AuthorizationContext, OrderIntent


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
    issued_at: datetime

    @classmethod
    def from_authorization(
        cls,
        *,
        intent: OrderIntent,
        authorization: AuthorizationContext,
        fence_token: Any,
    ) -> "TradeCertificate":
        expected_value = authorization.decision.expected_value
        if expected_value is None:
            raise ValueError("TRADE_CERTIFICATE_EXPECTED_VALUE_MISSING")
        certificate_id = f"trade-cert:{intent.intent_id}"
        return cls(
            certificate_id=certificate_id,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            strategy_id=authorization.decision.strategy_id,
            strategy_version=authorization.decision.strategy_version,
            strategy_hash=intent.strategy_hash,
            symbol=intent.symbol,
            direction=intent.direction,
            probability=authorization.decision.probability,
            expected_value=float(expected_value),
            stake=intent.stake,
            account_loginid=intent.account.loginid,
            account_currency=intent.account.currency,
            account_environment=intent.account.environment,
            market_snapshot_hash=authorization.decision.market_snapshot_hash,
            proposal_id=str(intent.proposal_id),
            authorization_id=authorization.authorization_id,
            config_hash=intent.config_hash,
            idempotency_key=intent.intent_id,
            fence_generation=int(fence_token.generation),
            fence_owner=str(fence_token.owner),
            issued_at=datetime.utcnow(),
        )

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issued_at"] = self.issued_at.isoformat()
        payload["certificate_hash"] = sha256(payload)
        return payload
