"""Strict, execution-neutral contracts between Layer 6 and the capital plane.

Layer 6 returns a risk verdict only. CapitalPlaneExecutor remains the sole
capital-moving authority and must independently enforce LIVE_LOCK, its durable
kill switch, reconciliation, fencing, idempotency, and broker-state checks.

SHA-256 provenance detects payload drift. It is not a digital signature and
does not authenticate an asserted source by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from runtime.core.authority import GateResult
from runtime.core.events import sha256
from runtime.core.fencing import FenceToken
from runtime.core.layer6_risk_gate import Layer6RiskGate, RiskPolicy, RiskRequest, RiskVerdict
from runtime.core.models import AccountIdentity, AuthorizationContext, CapitalSnapshot, Decision, OrderIntent

if TYPE_CHECKING:
    from runtime.broker.executor import ExecutionOutcome


RISK_INPUT_SCHEMA = "aurelia.layer6.risk_input.v1"
RISK_POLICY_SCHEMA = "aurelia.layer6.risk_policy.v1"
ACCOUNT_CURRENCY_UNIT = "ACCOUNT_CURRENCY"


@dataclass(frozen=True)
class RiskProvenance:
    """Integrity and freshness metadata for one immutable payload snapshot."""

    source_id: str
    captured_at_utc: datetime
    schema_version: str
    checksum_sha256: str
    currency: str
    unit: str = ACCOUNT_CURRENCY_UNIT


@dataclass(frozen=True)
class RiskEvaluationInput:
    """A risk request plus provenance covering every numeric/exposure field."""

    risk_request: RiskRequest
    provenance: RiskProvenance


@runtime_checkable
class IRiskEngine(Protocol):
    """Layer 6 port: deterministic evaluation only, with no capital authority."""

    def evaluate_order(self, input_data: RiskEvaluationInput) -> RiskVerdict:
        ...


@runtime_checkable
class IExecutionGateway(Protocol):
    """Contract of the existing canonical capital-plane executor.

    This protocol deliberately has no raw broker submit/buy method and no
    capital getter for the risk engine. The concrete gateway must repeat the
    release, kill-switch, reconciliation, balance, idempotency and fencing
    checks immediately before any broker submission.
    """

    kill_switch: bool

    def release_allows_live(self) -> bool:
        ...

    async def authorize_and_build_intent(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        runtime_config_hash: str,
        account: AccountIdentity,
        risk_approved: bool,
        firewall_approved: bool,
        reconciliation_healthy: bool,
        final_execution_authorization: bool,
        live_trading_enabled: bool,
        probability_calibrated: bool = False,
        probability_fresh: bool = False,
        probability_drift_ok: bool = False,
        market_data_validated: bool = False,
        exposure_approved: bool = False,
        proposal_id: str | None = None,
        mode: str = "LIVE",
    ) -> tuple[GateResult, AuthorizationContext | None, OrderIntent | None]:
        ...

    async def execute(
        self,
        intent: OrderIntent,
        context: AuthorizationContext,
        fence_token: FenceToken,
    ) -> ExecutionOutcome:
        ...


class Layer6RiskEngine:
    """Source-bound adapter around the existing fail-closed Layer6RiskGate.

    enabled defaults to False. Expected source IDs and account currency are
    explicit constructor inputs, not inferred from the risk request. Inputs
    with missing, stale/future, malformed, cross-currency, wrong-source,
    wrong-schema, or checksum-mismatched provenance are denied.
    """

    def __init__(
        self,
        policy: RiskPolicy,
        *,
        policy_provenance: RiskProvenance,
        account_currency: str,
        expected_policy_source_id: str,
        expected_input_source_id: str,
        enabled: bool = False,
        max_input_age_seconds: float = 15.0,
    ) -> None:
        currency = str(account_currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("LAYER6_ACCOUNT_CURRENCY_INVALID")
        if not isinstance(expected_policy_source_id, str) or not expected_policy_source_id.strip():
            raise ValueError("LAYER6_EXPECTED_POLICY_SOURCE_REQUIRED")
        if not isinstance(expected_input_source_id, str) or not expected_input_source_id.strip():
            raise ValueError("LAYER6_EXPECTED_INPUT_SOURCE_REQUIRED")
        if isinstance(max_input_age_seconds, bool) or not isinstance(max_input_age_seconds, (int, float)):
            raise ValueError("LAYER6_MAX_INPUT_AGE_INVALID")
        try:
            max_age = float(max_input_age_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("LAYER6_MAX_INPUT_AGE_INVALID") from exc
        if not isfinite(max_age) or max_age <= 0:
            raise ValueError("LAYER6_MAX_INPUT_AGE_INVALID")
        if not isinstance(policy, RiskPolicy):
            raise TypeError("LAYER6_RISK_POLICY_REQUIRED")
        self.policy = policy
        self.policy_provenance = policy_provenance
        self.account_currency = currency
        self.expected_policy_source_id = expected_policy_source_id
        self.expected_input_source_id = expected_input_source_id
        self.max_input_age_seconds = max_age
        self._gate = Layer6RiskGate(policy, enabled=enabled)

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def _provenance_error(
        self,
        provenance: RiskProvenance,
        *,
        payload: dict,
        expected_source_id: str,
        expected_schema: str,
        prefix: str,
        now: datetime,
    ) -> str | None:
        if not isinstance(provenance, RiskProvenance):
            return f"{prefix}_PROVENANCE_MISSING"
        if not isinstance(provenance.source_id, str) or not provenance.source_id.strip():
            return f"{prefix}_SOURCE_ID_MISSING"
        if provenance.source_id != expected_source_id:
            return f"{prefix}_SOURCE_MISMATCH"
        if provenance.schema_version != expected_schema:
            return f"{prefix}_SCHEMA_MISMATCH"
        if provenance.currency != self.account_currency or provenance.unit != ACCOUNT_CURRENCY_UNIT:
            return f"{prefix}_CURRENCY_OR_UNIT_MISMATCH"
        if not isinstance(provenance.captured_at_utc, datetime) or provenance.captured_at_utc.tzinfo is None:
            return f"{prefix}_TIMESTAMP_INVALID"
        try:
            age = (now - provenance.captured_at_utc.astimezone(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return f"{prefix}_TIMESTAMP_INVALID"
        if not isfinite(age) or age < 0 or age > self.max_input_age_seconds:
            return f"{prefix}_STALE_OR_FUTURE"
        checksum = provenance.checksum_sha256
        if (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in "0123456789abcdef" for character in checksum)
        ):
            return f"{prefix}_CHECKSUM_MISMATCH"
        try:
            actual_checksum = sha256(payload)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return f"{prefix}_PAYLOAD_UNHASHABLE"
        if checksum != actual_checksum:
            return f"{prefix}_CHECKSUM_MISMATCH"
        return None

    def _reject(self, reason: str, started: float) -> RiskVerdict:
        elapsed_ms = max(0.0, (perf_counter() - started) * 1000.0)
        return RiskVerdict(
            risk_approved=False,
            reason=reason,
            evaluated_at_utc=self._now_utc().isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            latency_ms=round(elapsed_ms, 3),
        )

    def evaluate_order(self, input_data: RiskEvaluationInput) -> RiskVerdict:
        """Evaluate a source-bound request; return a risk verdict only."""
        started = perf_counter()
        if not isinstance(input_data, RiskEvaluationInput):
            return self._reject("RISK_INPUT_ENVELOPE_INVALID", started)
        if not isinstance(input_data.risk_request, RiskRequest):
            return self._reject("RISK_REQUEST_INVALID", started)

        now = self._now_utc()
        policy_error = self._provenance_error(
            self.policy_provenance,
            payload=asdict(self.policy),
            expected_source_id=self.expected_policy_source_id,
            expected_schema=RISK_POLICY_SCHEMA,
            prefix="RISK_POLICY",
            now=now,
        )
        if policy_error:
            return self._reject(policy_error, started)

        input_error = self._provenance_error(
            input_data.provenance,
            payload=asdict(input_data.risk_request),
            expected_source_id=self.expected_input_source_id,
            expected_schema=RISK_INPUT_SCHEMA,
            prefix="RISK_INPUT",
            now=now,
        )
        if input_error:
            return self._reject(input_error, started)

        return self._gate.evaluate(input_data.risk_request)
