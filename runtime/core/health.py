from dataclasses import dataclass, field
from datetime import datetime, timezone

from runtime.core.models import CapitalSnapshot


@dataclass
class HealthSnapshot:
    process_heartbeat: datetime
    broker_session: bool = False
    market_data_fresh: bool = False
    capital_fresh: bool = False
    ledger_healthy: bool = False
    reconciliation_healthy: bool = False
    kill_switch_off: bool = False
    executor_lease_valid: bool = True
    resource_ok: bool = True
    dependencies_ok: bool = True
    agent_workers_healthy: bool = True
    critical_unknowns: set[str] = field(default_factory=set)

    def liveness(self):
        return (datetime.now(timezone.utc) - self.process_heartbeat).total_seconds() < 30

    def readiness(self):
        return (
            self.liveness()
            and self.dependencies_ok
            and self.resource_ok
            and self.executor_lease_valid
            and self.agent_workers_healthy
            and not self.critical_unknowns
        )

    def can_open_new_exposure(self):
        return (
            self.readiness()
            and self.broker_session
            and self.market_data_fresh
            and self.capital_fresh
            and self.ledger_healthy
            and self.reconciliation_healthy
            and self.kill_switch_off
        )


def refresh_runtime_health(
    health: HealthSnapshot,
    *,
    broker_session: bool,
    capital: CapitalSnapshot | None,
    market_data_received_at: datetime | None,
    ledger_healthy: bool,
    reconciliation_healthy: bool,
    kill_switch_off: bool,
    market_data_max_age_seconds: float = 5.0,
) -> HealthSnapshot:
    """Apply evidence-backed runtime observations to the operational health snapshot."""
    health.broker_session = bool(broker_session)
    health.capital_fresh = bool(capital is not None and capital.is_valid())
    if market_data_received_at is None:
        health.market_data_fresh = False
    else:
        age = (datetime.now(timezone.utc) - market_data_received_at).total_seconds()
        health.market_data_fresh = 0 <= age <= market_data_max_age_seconds
    health.ledger_healthy = bool(ledger_healthy)
    health.reconciliation_healthy = bool(reconciliation_healthy)
    health.kill_switch_off = bool(kill_switch_off)
    return health
