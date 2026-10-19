"""Deterministic, fail-closed REFLEX risk gate for paper evaluation only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
import re

from .decision import JevDecision

# Preserve AURELIA policy: 1% planned risk by default, 2% absolute ceiling.
DEFAULT_MAX_POSITION_PCT = 1.0
ABSOLUTE_MAX_POSITION_PCT = 2.0
DAILY_LOSS_LIMIT_PCT = 3.0
MAX_DRAWDOWN_PCT = 15.0
MIN_CONFIDENCE = 0.70
MAX_ACCEPTED_PROBABILITY = 0.75
KILL_CONFIDENCE_FLOOR = 0.50
MIN_SETUP_QUALITY = 2


class RiskSnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    """Risk inputs come from local ledger/reconciled account state.

    Amounts use one consistent account currency. A production caller must not
    fabricate equity or use stale/unverified broker balance for live sizing.
    """
    equity: float
    day_start_equity: float
    peak_equity: float
    daily_pnl: float
    api_healthy: bool = True
    consecutive_losses: int = 0
    observed_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for name in ("equity", "day_start_equity", "peak_equity", "daily_pnl"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RiskSnapshotError(f"{name.upper()}_MUST_BE_NUMERIC")
            if not isfinite(float(value)):
                raise RiskSnapshotError(f"{name.upper()}_MUST_BE_FINITE")
        if self.equity <= 0 or self.day_start_equity <= 0 or self.peak_equity <= 0:
            raise RiskSnapshotError("EQUITY_VALUES_MUST_BE_POSITIVE")
        if not isinstance(self.api_healthy, bool):
            raise RiskSnapshotError("API_HEALTHY_MUST_BE_BOOLEAN")
        if (
            isinstance(self.consecutive_losses, bool)
            or not isinstance(self.consecutive_losses, int)
            or self.consecutive_losses < 0
        ):
            raise RiskSnapshotError("CONSECUTIVE_LOSSES_INVALID")
        if not isinstance(self.observed_at_utc, datetime) or self.observed_at_utc.tzinfo is None:
            raise RiskSnapshotError("RISK_SNAPSHOT_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")

    def is_valid(self, max_age_seconds: float = 15.0) -> bool:
        if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)):
            return False
        try:
            age = (datetime.now(timezone.utc) - self.observed_at_utc).total_seconds()
            limit = float(max_age_seconds)
        except (TypeError, ValueError, OverflowError):
            return False
        return isfinite(age) and isfinite(limit) and limit > 0 and 0 <= age <= limit


@dataclass(frozen=True)
class StrategyEvidence:
    """Qualification assertions bound to the exact strategy hash.

    This object is data, not a trust boundary. A caller must obtain its values
    from the canonical registry/calibration/cost/OOS evidence verifier; an LLM
    response must never be used as evidence.
    """
    probability_calibrated: bool = False
    probability_fresh: bool = False
    drift_ok: bool = False
    instrument_qualified: bool = False
    costs_verified: bool = False
    net_economics_positive: bool = False
    out_of_sample_qualified: bool = False
    strategy_hash: str = ""
    evidence_ids: tuple[str, ...] = ()

    def rejection_reasons(self, *, expected_strategy_hash: str | None) -> tuple[str, ...]:
        reasons: list[str] = []
        checks = (
            ("probability_calibrated", "PROBABILITY_UNCALIBRATED"),
            ("probability_fresh", "PROBABILITY_STALE"),
            ("drift_ok", "MODEL_OR_STRATEGY_DRIFT"),
            ("instrument_qualified", "INSTRUMENT_NOT_QUALIFIED"),
            ("costs_verified", "COST_PROFILE_UNVERIFIED"),
            ("net_economics_positive", "NET_EXPECTED_VALUE_NOT_POSITIVE"),
            ("out_of_sample_qualified", "OUT_OF_SAMPLE_NOT_QUALIFIED"),
        )
        for field_name, reason in checks:
            value = getattr(self, field_name)
            if not isinstance(value, bool):
                reasons.append(f"{field_name.upper()}_EVIDENCE_INVALID")
            elif not value:
                reasons.append(reason)
        if not isinstance(self.strategy_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", self.strategy_hash):
            reasons.append("STRATEGY_HASH_INVALID")
        if not isinstance(expected_strategy_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_strategy_hash):
            reasons.append("EXPECTED_STRATEGY_HASH_MISSING_OR_INVALID")
        elif isinstance(self.strategy_hash, str) and self.strategy_hash.lower() != expected_strategy_hash.lower():
            reasons.append("STRATEGY_EVIDENCE_HASH_MISMATCH")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or any(not isinstance(item, str) or not item.strip() for item in self.evidence_ids)
        ):
            reasons.append("QUALIFICATION_EVIDENCE_IDS_MISSING_OR_INVALID")
        return tuple(reasons)

    def as_dict(self) -> dict[str, object]:
        return {
            "probability_calibrated": self.probability_calibrated,
            "probability_fresh": self.probability_fresh,
            "drift_ok": self.drift_ok,
            "instrument_qualified": self.instrument_qualified,
            "costs_verified": self.costs_verified,
            "net_economics_positive": self.net_economics_positive,
            "out_of_sample_qualified": self.out_of_sample_qualified,
            "strategy_hash": self.strategy_hash,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    kill_switch_tripped: bool


class PaperReflexGate:
    """Hard-coded policy gate; deliberately has no order-submission method.

    kill_switch_armed means the triggers are active; tripped means the system
    is latched in a blocked state. This avoids confusing armed with halted.
    """

    def __init__(self, *, max_position_pct: float = DEFAULT_MAX_POSITION_PCT) -> None:
        if isinstance(max_position_pct, bool) or not isinstance(max_position_pct, (int, float)):
            raise ValueError("MAX_POSITION_PCT_MUST_BE_NUMERIC")
        if not isfinite(float(max_position_pct)) or not 0 < max_position_pct <= DEFAULT_MAX_POSITION_PCT:
            raise ValueError("MAX_POSITION_PCT_EXCEEDS_DEFAULT_POLICY")
        self.max_position_pct = float(max_position_pct)
        self.kill_switch_armed = True
        self.tripped = False
        self.trip_reasons: list[str] = []

    def trip(self, reason: str) -> None:
        if not self.kill_switch_armed:
            return
        normalized = str(reason).strip().upper() or "UNSPECIFIED_KILL_TRIGGER"
        self.tripped = True
        if normalized not in self.trip_reasons:
            self.trip_reasons.append(normalized)

    def on_api_error(self) -> None:
        self.trip("API_ERROR")

    def evaluate(
        self, decision: JevDecision, snapshot: PortfolioRiskSnapshot, *,
        evidence: StrategyEvidence | None = None,
        expected_strategy_hash: str | None = None,
    ) -> GateResult:
        reasons: list[str] = []
        if not snapshot.is_valid():
            self.trip("RISK_SNAPSHOT_STALE_OR_INVALID")
        if not snapshot.api_healthy:
            self.on_api_error()
        if snapshot.consecutive_losses >= 3:
            self.trip("CONSECUTIVE_LOSS_LIMIT_REACHED")
        if decision.confidence < KILL_CONFIDENCE_FLOOR:
            self.trip("CONFIDENCE_BELOW_0_50")
        if decision.regime == "crisis":
            self.trip("CRISIS_REGIME")

        if self.tripped:
            reasons.extend(self.trip_reasons)
            reasons.append("KILL_SWITCH_LATCHED")
            return GateResult(False, "BLOCKED", tuple(dict.fromkeys(reasons)), True)

        daily_loss_pct = max(0.0, -float(snapshot.daily_pnl)) / float(snapshot.day_start_equity) * 100.0
        effective_peak = max(float(snapshot.peak_equity), float(snapshot.equity))
        drawdown_pct = max(0.0, effective_peak - float(snapshot.equity)) / effective_peak * 100.0
        if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
            self.trip("DAILY_LOSS_LIMIT_REACHED")
            reasons.extend([*self.trip_reasons, "KILL_SWITCH_LATCHED"])
            return GateResult(False, "BLOCKED", tuple(dict.fromkeys(reasons)), True)
        if drawdown_pct >= MAX_DRAWDOWN_PCT:
            self.trip("MAX_DRAWDOWN_REACHED")
            reasons.extend([*self.trip_reasons, "KILL_SWITCH_LATCHED"])
            return GateResult(False, "BLOCKED", tuple(dict.fromkeys(reasons)), True)

        if decision.direction == "neutral":
            reasons.append("NEUTRAL_SIGNAL")
        if decision.setup_quality < MIN_SETUP_QUALITY:
            reasons.append("SETUP_QUALITY_BELOW_2")
        if decision.confidence < MIN_CONFIDENCE:
            reasons.append("CONFIDENCE_BELOW_0_70")
        if decision.confidence > MAX_ACCEPTED_PROBABILITY:
            reasons.append("PROBABILITY_ABOVE_AURELIA_MAX_0_75")
        if decision.risk_state != "safe":
            reasons.append("RISK_STATE_NOT_SAFE")
        if evidence is None:
            reasons.append("STRATEGY_EVIDENCE_MISSING")
        else:
            reasons.extend(evidence.rejection_reasons(expected_strategy_hash=expected_strategy_hash))
        if decision.position_size_pct > self.max_position_pct:
            reasons.append("POSITION_SIZE_ABOVE_DEFAULT_1_PERCENT_POLICY")
        if decision.position_size_pct > ABSOLUTE_MAX_POSITION_PCT:
            reasons.append("ABSOLUTE_POSITION_SIZE_CEILING_BREACHED")

        allowed = not reasons
        return GateResult(
            allowed=allowed, status="WOULD_TRADE" if allowed else "HOLD",
            reasons=tuple(reasons or ["ALL_PAPER_GATES_PASSED"]),
            kill_switch_tripped=self.tripped,
        )

    def reset_after_operator_review(
        self, *, operator_approval_id: str, snapshot: PortfolioRiskSnapshot,
        crisis_cleared: bool, confidence_recovered: bool,
    ) -> None:
        """Clear the latch only with a human approval reference and healthy state."""
        if not isinstance(operator_approval_id, str) or not operator_approval_id.strip():
            raise ValueError("OPERATOR_APPROVAL_REFERENCE_REQUIRED")
        if not isinstance(crisis_cleared, bool) or not crisis_cleared:
            raise ValueError("CRISIS_CLEARANCE_REQUIRED")
        if not isinstance(confidence_recovered, bool) or not confidence_recovered:
            raise ValueError("CONFIDENCE_RECOVERY_REQUIRED")
        if not snapshot.is_valid():
            raise ValueError("CURRENT_RISK_SNAPSHOT_REQUIRED")
        if not snapshot.api_healthy:
            raise ValueError("API_HEALTH_MUST_BE_RESTORED")
        daily_loss_pct = max(0.0, -float(snapshot.daily_pnl)) / float(snapshot.day_start_equity) * 100.0
        effective_peak = max(float(snapshot.peak_equity), float(snapshot.equity))
        drawdown_pct = max(0.0, effective_peak - float(snapshot.equity)) / effective_peak * 100.0
        if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
            raise ValueError("DAILY_LOSS_HARD_STOP_CANNOT_BE_OVERRIDDEN")
        if snapshot.consecutive_losses >= 3:
            raise ValueError("CONSECUTIVE_LOSS_HARD_STOP_CANNOT_BE_OVERRIDDEN")
        if drawdown_pct >= MAX_DRAWDOWN_PCT:
            raise ValueError("MAX_DRAWDOWN_HARD_STOP_REQUIRES_NEW_RISK_STATE")
        self.tripped = False
        self.trip_reasons.clear()
