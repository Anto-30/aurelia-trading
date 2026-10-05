from __future__ import annotations

"""Deterministic, execution-neutral FOMO-style memecoin research contracts.

This module intentionally stops at a research classification. It has no broker,
wallet, capital, or live-lock access and cannot produce an execution command.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum


RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
MIN_TRADE_PROBABILITY = 0.55
MAX_TRADE_PROBABILITY = 0.75


class ResearchStatus(str, Enum):
    RESEARCH_QUALIFIED = "RESEARCH_QUALIFIED"
    RESEARCH_REJECTED = "RESEARCH_REJECTED"
    UNKNOWN = "UNKNOWN"


class EvidenceClass(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SIMULATION_VERIFIED = "SIMULATION_VERIFIED"


def _finite_non_negative(value: float, field: str) -> float:
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be finite")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _ratio(value: float, field: str) -> float:
    value = float(value)
    if value != value or value < 0 or value > 1:
        raise ValueError(f"{field} must be in [0, 1]")
    return value


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceRef:
    source: str
    source_timestamp_utc: str
    collected_timestamp_utc: str
    verified: bool

    def validate(self) -> None:
        if not self.source.strip():
            raise ValueError("evidence source is required")
        source_ts = _timestamp(self.source_timestamp_utc, "source_timestamp_utc")
        collected_ts = _timestamp(self.collected_timestamp_utc, "collected_timestamp_utc")
        if collected_ts < source_ts:
            raise ValueError("collected timestamp cannot precede source timestamp")
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be boolean")


@dataclass(frozen=True)
class TokenSafety:
    identity_verified: bool
    mint_authority_revoked: bool | None
    freeze_authority_revoked: bool | None
    upgradeability_known: bool
    liquidity_control_known: bool
    critical_flags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.identity_verified, bool):
            raise ValueError("identity_verified must be boolean")
        if self.mint_authority_revoked not in (True, False, None):
            raise ValueError("mint_authority_revoked must be boolean or None")
        if self.freeze_authority_revoked not in (True, False, None):
            raise ValueError("freeze_authority_revoked must be boolean or None")
        if not isinstance(self.upgradeability_known, bool):
            raise ValueError("upgradeability_known must be boolean")
        if not isinstance(self.liquidity_control_known, bool):
            raise ValueError("liquidity_control_known must be boolean")
        if any(not flag.strip() for flag in self.critical_flags):
            raise ValueError("critical safety flags cannot be empty")


@dataclass(frozen=True)
class MarketMetrics:
    market_cap_usd: float
    liquidity_usd: float
    volume_24h_usd: float
    spread_bps: float
    slippage_bps: float
    price_impact_bps: float
    execution_degradation_bps: float
    exitability_score: float

    def validate(self) -> None:
        for name in (
            "market_cap_usd",
            "liquidity_usd",
            "volume_24h_usd",
            "spread_bps",
            "slippage_bps",
            "price_impact_bps",
            "execution_degradation_bps",
        ):
            _finite_non_negative(getattr(self, name), name)
        _ratio(self.exitability_score, "exitability_score")


@dataclass(frozen=True)
class HolderMetrics:
    holder_count: int
    top10_concentration: float
    wallet_concentration: float

    def validate(self) -> None:
        if int(self.holder_count) < 0:
            raise ValueError("holder_count must be non-negative")
        _ratio(self.top10_concentration, "top10_concentration")
        _ratio(self.wallet_concentration, "wallet_concentration")


@dataclass(frozen=True)
class TraderMetrics:
    completed_trades: int
    realized_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float | None
    expectancy: float
    median_hold_seconds: float

    def validate(self) -> None:
        if int(self.completed_trades) < 0:
            raise ValueError("completed_trades must be non-negative")
        _finite_non_negative(self.max_drawdown, "max_drawdown")
        _ratio(self.win_rate, "win_rate")
        if self.profit_factor is not None:
            _finite_non_negative(self.profit_factor, "profit_factor")
        for name in ("realized_return", "expectancy"):
            value = float(getattr(self, name))
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{name} must be finite")
        _finite_non_negative(self.median_hold_seconds, "median_hold_seconds")


@dataclass(frozen=True)
class SocialMetrics:
    independently_verified_sources: int
    source_credibility: float
    novelty: float
    engagement_quality: float
    contradiction_rate: float

    def validate(self) -> None:
        if int(self.independently_verified_sources) < 0:
            raise ValueError("independently_verified_sources must be non-negative")
        _ratio(self.source_credibility, "source_credibility")
        _ratio(self.novelty, "novelty")
        _ratio(self.engagement_quality, "engagement_quality")
        _ratio(self.contradiction_rate, "contradiction_rate")


@dataclass(frozen=True)
class MemecoinResearchCandidate:
    candidate_id: str
    token_mint: str
    chain: str
    narrative: str
    catalyst: str
    thesis: str
    invalidation: str
    gross_expected_return: float
    fees: float
    slippage_cost: float
    market_impact_cost: float
    execution_degradation_cost: float
    market: MarketMetrics
    holders: HolderMetrics
    safety: TokenSafety
    evidence: tuple[EvidenceRef, ...]
    probability: float | None = None
    probability_is_calibrated: bool = False
    trader: TraderMetrics | None = None
    social: SocialMetrics | None = None
    trend_only: bool = False


@dataclass(frozen=True)
class MemecoinResearchDecision:
    schema: str
    candidate_id: str
    token_mint: str
    chain: str
    status: ResearchStatus
    evidence_class: EvidenceClass
    reasons: tuple[str, ...]
    net_expected_edge: float | None
    calibrated_probability: float | None
    trade_probability_valid: bool
    execution_authorized: bool
    authorization_scope: str
    provenance_hash: str


def net_expected_edge(
    gross_expected_return: float,
    fees: float,
    slippage_cost: float,
    market_impact_cost: float,
    execution_degradation_cost: float,
) -> float:
    values = {
        "gross_expected_return": float(gross_expected_return),
        "fees": _finite_non_negative(fees, "fees"),
        "slippage_cost": _finite_non_negative(slippage_cost, "slippage_cost"),
        "market_impact_cost": _finite_non_negative(market_impact_cost, "market_impact_cost"),
        "execution_degradation_cost": _finite_non_negative(
            execution_degradation_cost, "execution_degradation_cost"
        ),
    }
    gross = values["gross_expected_return"]
    if gross != gross or gross in (float("inf"), float("-inf")):
        raise ValueError("gross_expected_return must be finite")
    return gross - sum(
        values[name]
        for name in (
            "fees",
            "slippage_cost",
            "market_impact_cost",
            "execution_degradation_cost",
        )
    )


def validate_calibrated_probability(
    probability: float | None,
    *,
    calibrated: bool,
    minimum: float = MIN_TRADE_PROBABILITY,
    maximum: float = MAX_TRADE_PROBABILITY,
) -> bool:
    if probability is None or not calibrated:
        return False
    probability = float(probability)
    return (
        probability == probability
        and probability not in (float("inf"), float("-inf"))
        and minimum <= probability <= maximum
    )


def social_quality_score(metrics: SocialMetrics | None) -> float | None:
    if metrics is None:
        return None
    metrics.validate()
    return (
        0.30 * metrics.source_credibility
        + 0.20 * metrics.novelty
        + 0.25 * metrics.engagement_quality
        + 0.25 * (1.0 - metrics.contradiction_rate)
    )


def trader_quality_score(metrics: TraderMetrics | None) -> float | None:
    if metrics is None or metrics.completed_trades <= 0:
        return None
    metrics.validate()
    expectancy_score = 1.0 if metrics.expectancy > 0 else 0.0
    drawdown_score = max(0.0, 1.0 - min(1.0, metrics.max_drawdown))
    profit_factor_score = (
        min(1.0, metrics.profit_factor / 2.0) if metrics.profit_factor is not None else 0.0
    )
    return (
        0.30 * metrics.win_rate
        + 0.25 * expectancy_score
        + 0.20 * drawdown_score
        + 0.15 * profit_factor_score
        + 0.10 * min(1.0, metrics.completed_trades / 100.0)
    )


def _payload(decision_fields: dict) -> str:
    return json.dumps(
        decision_fields,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def research_candidate(
    candidate: MemecoinResearchCandidate,
    *,
    min_liquidity_usd: float = 50_000.0,
    max_top10_concentration: float = 0.50,
    max_wallet_concentration: float = 0.70,
    min_holder_count: int = 100,
    min_exitability_score: float = 0.60,
) -> MemecoinResearchDecision:
    reasons: list[str] = []
    candidate.market.validate()
    candidate.holders.validate()
    candidate.safety.validate()
    for evidence in candidate.evidence:
        evidence.validate()

    if candidate.chain.lower() != "solana":
        reasons.append("CHAIN_NOT_IN_SCOPE")
    if not candidate.token_mint.strip():
        reasons.append("TOKEN_IDENTITY_MISSING")
    if not candidate.narrative.strip() or not candidate.catalyst.strip():
        reasons.append("THESIS_CONTEXT_INCOMPLETE")
    if not candidate.thesis.strip() or not candidate.invalidation.strip():
        reasons.append("THESIS_OR_INVALIDATION_MISSING")
    if not candidate.evidence:
        reasons.append("EVIDENCE_MISSING")
    elif not all(item.verified for item in candidate.evidence):
        reasons.append("UNVERIFIED_EVIDENCE")
    if not candidate.safety.identity_verified:
        reasons.append("TOKEN_IDENTITY_UNVERIFIED")
    if candidate.safety.mint_authority_revoked is None:
        reasons.append("MINT_AUTHORITY_UNKNOWN")
    elif candidate.safety.mint_authority_revoked is False:
        reasons.append("MINT_AUTHORITY_ACTIVE")
    if candidate.safety.freeze_authority_revoked is None:
        reasons.append("FREEZE_AUTHORITY_UNKNOWN")
    elif candidate.safety.freeze_authority_revoked is False:
        reasons.append("FREEZE_AUTHORITY_ACTIVE")
    if not candidate.safety.upgradeability_known:
        reasons.append("UPGRADEABILITY_UNKNOWN")
    if not candidate.safety.liquidity_control_known:
        reasons.append("LIQUIDITY_CONTROL_UNKNOWN")
    if candidate.safety.critical_flags:
        reasons.append("CRITICAL_TOKEN_SAFETY_FLAG")
    if candidate.market.liquidity_usd < min_liquidity_usd:
        reasons.append("LIQUIDITY_BELOW_THRESHOLD")
    if candidate.market.exitability_score < min_exitability_score:
        reasons.append("EXITABILITY_TOO_LOW")
    if candidate.holders.holder_count < min_holder_count:
        reasons.append("HOLDER_COUNT_TOO_LOW")
    if candidate.holders.top10_concentration > max_top10_concentration:
        reasons.append("TOP10_CONCENTRATION_TOO_HIGH")
    if candidate.holders.wallet_concentration > max_wallet_concentration:
        reasons.append("WALLET_CONCENTRATION_TOO_HIGH")
    if candidate.trend_only:
        reasons.append("TREND_ONLY_NO_THESIS")

    edge = net_expected_edge(
        candidate.gross_expected_return,
        candidate.fees,
        candidate.slippage_cost,
        candidate.market_impact_cost,
        candidate.execution_degradation_cost,
    )
    if edge <= 0:
        reasons.append("NET_EXPECTED_EDGE_NON_POSITIVE")

    probability_valid = validate_calibrated_probability(
        candidate.probability,
        calibrated=candidate.probability_is_calibrated,
    )
    if not probability_valid:
        reasons.append("TRADE_PROBABILITY_INVALID_OR_UNCALIBRATED")

    if candidate.social is not None:
        candidate.social.validate()
    if candidate.trader is not None:
        candidate.trader.validate()

    if reasons:
        status = (
            ResearchStatus.UNKNOWN
            if any(reason.endswith("UNKNOWN") or reason in {
                "EVIDENCE_MISSING",
                "UNVERIFIED_EVIDENCE",
                "TRADE_PROBABILITY_INVALID_OR_UNCALIBRATED",
            } for reason in reasons)
            else ResearchStatus.RESEARCH_REJECTED
        )
    else:
        status = ResearchStatus.RESEARCH_QUALIFIED

    fields = {
        "schema": "aurelia.memecoin_research_decision.v1",
        "candidate_id": candidate.candidate_id,
        "token_mint": candidate.token_mint,
        "chain": candidate.chain,
        "status": status.value,
        "evidence_class": EvidenceClass.RESEARCH_ONLY.value,
        "reasons": sorted(reasons),
        "net_expected_edge": edge,
        "calibrated_probability": candidate.probability if probability_valid else None,
        "trade_probability_valid": probability_valid,
        "execution_authorized": False,
        "authorization_scope": "RESEARCH_ONLY",
    }
    provenance_hash = hashlib.sha256(_payload(fields).encode("utf-8")).hexdigest()
    return MemecoinResearchDecision(**fields, provenance_hash=provenance_hash)


def research_decision_cannot_authorize_execution(
    decision: MemecoinResearchDecision,
) -> None:
    if decision.execution_authorized:
        raise AssertionError("research decision cannot authorize execution")
    if decision.authorization_scope != "RESEARCH_ONLY":
        raise AssertionError("research decision has invalid authorization scope")
