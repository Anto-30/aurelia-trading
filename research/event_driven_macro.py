from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

MIN_TRADE_PROBABILITY = 0.55
MAX_TRADE_PROBABILITY = 0.75


class ResultStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"


class Scenario(str, Enum):
    GOP_RETENTION = "GOP_RETENTION"
    DIVIDED_GOVERNMENT = "DIVIDED_GOVERNMENT"
    DEMOCRATIC_SWEEP = "DEMOCRATIC_SWEEP"
    UNRESOLVED = "UNRESOLVED"


class MacroRegime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class Action(str, Enum):
    TRADE_CANDIDATE = "TRADE_CANDIDATE"
    HEDGE = "HEDGE"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class PoliticalSnapshot:
    house_dem_probability: float
    senate_dem_probability: float
    house_status: ResultStatus = ResultStatus.UNKNOWN
    senate_status: ResultStatus = ResultStatus.UNKNOWN
    contested: bool = False
    as_of_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketSnapshot:
    spx_return_pct: float | None = None
    nasdaq_return_pct: float | None = None
    small_cap_return_pct: float | None = None
    two_year_yield_change_bps: float | None = None
    ten_year_yield_change_bps: float | None = None
    usd_return_pct: float | None = None
    gold_return_pct: float | None = None
    oil_return_pct: float | None = None
    credit_spread_change_bps: float | None = None
    vix_level: float | None = None
    vix_change_pct: float | None = None
    crypto_return_pct: float | None = None
    as_of_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CompanyExposure:
    company: str
    industry: str
    policy: str
    revenue_exposure_pct: float
    earnings_direction: str
    evidence_id: str


@dataclass(frozen=True)
class MacroPolicy:
    political_staleness_hours: float = 24.0
    market_staleness_minutes: float = 10.0
    minimum_cross_asset_observations: int = 4
    surprise_trade_threshold: float = 25.0
    high_surprise_threshold: float = 50.0
    minimum_confirmation_score: int = 4
    hard_no_trade_on_contested: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "MacroPolicy":
        staleness = data.get("staleness", {})
        confirmation = data.get("confirmation", {})
        surprise = data.get("surprise", {})
        staleness = staleness if isinstance(staleness, Mapping) else {}
        confirmation = confirmation if isinstance(confirmation, Mapping) else {}
        surprise = surprise if isinstance(surprise, Mapping) else {}
        return cls(
            political_staleness_hours=float(staleness.get("political_hours", cls.political_staleness_hours)),
            market_staleness_minutes=float(staleness.get("market_minutes", cls.market_staleness_minutes)),
            minimum_cross_asset_observations=int(confirmation.get("minimum_observations", cls.minimum_cross_asset_observations)),
            minimum_confirmation_score=int(confirmation.get("minimum_score", cls.minimum_confirmation_score)),
            surprise_trade_threshold=float(surprise.get("trade_threshold", cls.surprise_trade_threshold)),
            high_surprise_threshold=float(surprise.get("high_threshold", cls.high_surprise_threshold)),
            hard_no_trade_on_contested=bool(data.get("hard_no_trade_on_contested", cls.hard_no_trade_on_contested)),
        )


def _finite_probability(value: float) -> bool:
    return not isinstance(value, bool) and isfinite(value) and 0.0 <= value <= 1.0


def probability_eligible(probability: float) -> bool:
    return not isinstance(probability, bool) and isfinite(probability) and MIN_TRADE_PROBABILITY <= probability <= MAX_TRADE_PROBABILITY


def _age_hours(ts: datetime, now: datetime) -> float:
    if ts.tzinfo is None or now.tzinfo is None:
        raise ValueError("TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return max(0.0, (now - ts.astimezone(timezone.utc)).total_seconds() / 3600.0)


def classify_scenario(snapshot: PoliticalSnapshot) -> Scenario:
    if snapshot.contested or ResultStatus.CONTESTED in {snapshot.house_status, snapshot.senate_status}:
        return Scenario.UNRESOLVED
    if ResultStatus.UNKNOWN in {snapshot.house_status, snapshot.senate_status}:
        return Scenario.UNRESOLVED
    house_dem = snapshot.house_status == ResultStatus.CONFIRMED
    senate_dem = snapshot.senate_status == ResultStatus.CONFIRMED
    if house_dem and senate_dem:
        return Scenario.DEMOCRATIC_SWEEP
    if house_dem != senate_dem:
        return Scenario.DIVIDED_GOVERNMENT
    return Scenario.GOP_RETENTION


def _binary_outcome(status: ResultStatus, probability: float) -> float:
    return 1.0 if status == ResultStatus.CONFIRMED else probability


def political_surprise(previous: PoliticalSnapshot, current: PoliticalSnapshot) -> float:
    house_delta = abs(
        _binary_outcome(current.house_status, current.house_dem_probability)
        - _binary_outcome(previous.house_status, previous.house_dem_probability)
    )
    senate_delta = abs(
        _binary_outcome(current.senate_status, current.senate_dem_probability)
        - _binary_outcome(previous.senate_status, previous.senate_dem_probability)
    )
    return round(50.0 * (house_delta + senate_delta), 2)


def scenario_probabilities(snapshot: PoliticalSnapshot) -> dict[Scenario, float]:
    if not _finite_probability(snapshot.house_dem_probability) or not _finite_probability(snapshot.senate_dem_probability):
        raise ValueError("POLITICAL_PROBABILITY_INVALID")
    h, s = snapshot.house_dem_probability, snapshot.senate_dem_probability
    result = {
        Scenario.DEMOCRATIC_SWEEP: h * s,
        Scenario.DIVIDED_GOVERNMENT: h * (1.0 - s) + (1.0 - h) * s,
        Scenario.GOP_RETENTION: (1.0 - h) * (1.0 - s),
        Scenario.UNRESOLVED: 0.0,
    }
    if abs(sum(result.values()) - 1.0) > 1e-12:
        raise ArithmeticError("SCENARIO_PRIOR_NOT_NORMALIZED")
    return result


def _risk_on_directional_count(market: MarketSnapshot) -> tuple[int, int]:
    positive = negative = 0
    for value in (market.spx_return_pct, market.nasdaq_return_pct, market.small_cap_return_pct):
        if value is not None:
            positive += value > 0
            negative += value < 0
    for value in (market.two_year_yield_change_bps, market.ten_year_yield_change_bps):
        if value is not None:
            positive += value < 20
            negative += value > 40
    if market.credit_spread_change_bps is not None:
        positive += market.credit_spread_change_bps < 0
        negative += market.credit_spread_change_bps > 10
    if market.vix_change_pct is not None:
        positive += market.vix_change_pct < 0
        negative += market.vix_change_pct > 10
    return int(positive), int(negative)


def macro_regime(market: MarketSnapshot, policy: MacroPolicy) -> MacroRegime:
    observed = sum(
        value is not None
        for value in (
            market.spx_return_pct,
            market.nasdaq_return_pct,
            market.small_cap_return_pct,
            market.two_year_yield_change_bps,
            market.ten_year_yield_change_bps,
            market.credit_spread_change_bps,
            market.vix_change_pct,
        )
    )
    if observed < policy.minimum_cross_asset_observations:
        return MacroRegime.UNKNOWN
    positive, negative = _risk_on_directional_count(market)
    if positive >= policy.minimum_confirmation_score and positive >= negative + 2:
        return MacroRegime.RISK_ON
    if negative >= policy.minimum_confirmation_score and negative >= positive + 2:
        return MacroRegime.RISK_OFF
    return MacroRegime.MIXED


def _direction(value: float | None, up: str = "UP", down: str = "DOWN") -> str:
    if value is None:
        return "UNKNOWN"
    if value > 0:
        return up
    if value < 0:
        return down
    return "FLAT"


def cross_asset_confirmation(market: MarketSnapshot) -> dict[str, str]:
    relative = "UNKNOWN"
    if market.small_cap_return_pct is not None and market.spx_return_pct is not None:
        spread = market.small_cap_return_pct - market.spx_return_pct
        relative = "OUTPERFORM" if spread > 0.25 else "UNDERPERFORM" if spread < -0.25 else "FLAT"
    return {
        "small_cap_relative": relative,
        "usd": _direction(market.usd_return_pct),
        "gold": _direction(market.gold_return_pct),
        "oil": _direction(market.oil_return_pct),
        "crypto": _direction(market.crypto_return_pct),
        "two_year_rates": _direction(market.two_year_yield_change_bps),
        "ten_year_rates": _direction(market.ten_year_yield_change_bps),
        "credit_spreads": _direction(market.credit_spread_change_bps, "WIDER", "TIGHTER"),
        "vix": _direction(market.vix_change_pct),
    }


def political_risk_score(*, surprise_score: float, scenario: Scenario, regime: MacroRegime, contested: bool) -> float:
    """Heuristic event-risk magnitude, not a directional return forecast."""
    score = max(0.0, min(100.0, surprise_score / 2.0))
    if contested or scenario == Scenario.UNRESOLVED:
        score += 25.0
    if regime == MacroRegime.RISK_OFF:
        score += 20.0
    elif regime == MacroRegime.MIXED:
        score += 10.0
    elif regime == MacroRegime.UNKNOWN:
        score += 15.0
    return round(min(100.0, score), 2)


def trade_expression_candidates(*, scenario: Scenario, regime: MacroRegime, surprise_score: float) -> tuple[str, ...]:
    if scenario == Scenario.UNRESOLVED or regime == MacroRegime.UNKNOWN:
        return ("WAIT_FOR_CONFIRMATION",)
    if regime == MacroRegime.RISK_OFF:
        return ("INDEX_HEDGE", "PROTECTIVE_PUT", "COLLAR", "DEFENSIVE_PAIR")
    if regime == MacroRegime.RISK_ON and surprise_score >= 50.0:
        return ("INDEX_LONG", "SECTOR_LONG", "DEFINED_RISK_CALL_SPREAD", "RELATIVE_VALUE_PAIR")
    if regime == MacroRegime.RISK_ON:
        return ("RELATIVE_VALUE_PAIR", "SELECTIVE_SECTOR_LONG", "WAIT_FOR_EARNINGS_CONFIRMATION")
    return ("RELATIVE_VALUE_PAIR", "WAIT_FOR_CONFIRMATION")


def sector_rotation(scenario: Scenario, regime: MacroRegime):
    base = {
        Scenario.GOP_RETENTION: ("Traditional Energy", "Defense", "AI Infrastructure", "Financials"),
        Scenario.DIVIDED_GOVERNMENT: ("Healthcare", "Defense", "Non-AI Technology"),
        Scenario.DEMOCRATIC_SWEEP: ("Healthcare", "Clean Energy", "Infrastructure"),
        Scenario.UNRESOLVED: (),
    }
    avoid = []
    if regime == MacroRegime.RISK_OFF:
        avoid += ["High-beta growth", "Highly levered small caps"]
    elif regime == MacroRegime.MIXED:
        avoid += ["High-conviction directional baskets"]
    elif regime == MacroRegime.UNKNOWN:
        avoid += ["All directional sector trades"]
    return {"candidate_sectors": tuple(base[scenario]), "avoid_or_hedge": tuple(avoid)}


def relative_value_candidates(scenario: Scenario) -> tuple[tuple[str, str], ...]:
    return {
        Scenario.DIVIDED_GOVERNMENT: (
            ("Healthcare", "Broad Market"),
            ("Defense", "Industrials"),
            ("Domestic Retail", "Import-Heavy Retail"),
        ),
        Scenario.DEMOCRATIC_SWEEP: (
            ("Clean Energy", "Traditional Energy"),
            ("Healthcare", "Broad Market"),
        ),
        Scenario.GOP_RETENTION: (
            ("Traditional Energy", "Clean Energy"),
            ("AI Infrastructure", "Non-AI Technology"),
        ),
        Scenario.UNRESOLVED: (),
    }[scenario]


def event_half_life_hours(event_type: str) -> int:
    return {
        "ELECTION_HEADLINE": 12,
        "ELECTION_RESULT": 120,
        "CONGRESSIONAL_COMPOSITION": 720,
        "LEGISLATION": 2160,
        "REGULATION": 4320,
        "COURT_DECISION": 720,
        "TARIFF_ACTION": 720,
        "FED_DECISION": 48,
        "GEOPOLITICAL_SHOCK": 168,
        "SANCTIONS": 720,
    }.get(event_type.upper(), 168)


@dataclass(frozen=True)
class EventDecision:
    action: Action
    scenario: Scenario
    macro_regime: MacroRegime
    surprise_score: float
    confidence_score: float
    persistence_score: float
    reasons: tuple[str, ...]
    sector_view: Mapping[str, tuple[str, ...]]
    relative_value: tuple[tuple[str, str], ...]
    political_age_hours: float
    market_age_minutes: float
    cross_asset: Mapping[str, str]
    political_risk_score: float
    trade_expressions: tuple[str, ...]
    source_ids: tuple[str, ...] = ()
    capital_authority: bool = False


def rank_company_exposures(
    exposures: Sequence[CompanyExposure], *, scenario: Scenario
) -> tuple[CompanyExposure, ...]:
    allowed = {
        Scenario.GOP_RETENTION: {
            "traditional_energy",
            "tariff_sensitive_domestic",
            "defense",
            "ai_infrastructure",
        },
        Scenario.DIVIDED_GOVERNMENT: {"healthcare", "defense", "non_ai_technology"},
        Scenario.DEMOCRATIC_SWEEP: {"healthcare", "clean_energy", "infrastructure"},
        Scenario.UNRESOLVED: set(),
    }[scenario]
    scored: list[tuple[float, CompanyExposure]] = []
    for exposure in exposures:
        pct = exposure.revenue_exposure_pct
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0.0 <= float(pct) <= 100.0:
            continue
        if not exposure.evidence_id.strip():
            continue
        direction = exposure.earnings_direction.strip().upper()
        if direction not in {"POSITIVE", "NEGATIVE", "NEUTRAL"}:
            continue
        industry = exposure.industry.strip().lower().replace("-", "_").replace(" ", "_")
        if industry not in allowed:
            continue
        signed = 1.0 if direction == "POSITIVE" else -1.0 if direction == "NEGATIVE" else 0.0
        scored.append((signed * float(pct), exposure))
    scored.sort(key=lambda item: (-abs(item[0]), item[1].company.lower()))
    return tuple(item[1] for item in scored)


class EventDrivenMacroEngine:
    """Research-plane event intelligence. It never authorizes capital."""

    def __init__(self, policy: MacroPolicy | None = None) -> None:
        self.policy = policy or MacroPolicy()

    def evaluate(
        self,
        *,
        previous: PoliticalSnapshot,
        current: PoliticalSnapshot,
        market: MarketSnapshot,
        now: datetime | None = None,
        event_type: str = "ELECTION_RESULT",
    ) -> EventDecision:
        now = now or datetime.now(timezone.utc)
        political_age = _age_hours(current.as_of_utc, now)
        market_age = _age_hours(market.as_of_utc, now) * 60.0
        reasons: list[str] = []
        if not _finite_probability(previous.house_dem_probability) or not _finite_probability(previous.senate_dem_probability):
            reasons.append("PREVIOUS_POLITICAL_PROBABILITY_INVALID")
        if not _finite_probability(current.house_dem_probability) or not _finite_probability(current.senate_dem_probability):
            reasons.append("CURRENT_POLITICAL_PROBABILITY_INVALID")
        scenario = classify_scenario(current)
        regime = macro_regime(market, self.policy)
        surprise = political_surprise(previous, current)
        observed = sum(
            value is not None
            for value in (
                market.spx_return_pct,
                market.nasdaq_return_pct,
                market.small_cap_return_pct,
                market.two_year_yield_change_bps,
                market.ten_year_yield_change_bps,
                market.credit_spread_change_bps,
                market.vix_change_pct,
            )
        )
        completeness = observed / 7.0
        confidence = round(
            100.0
            * (
                0.4 * completeness
                + 0.3 * (scenario != Scenario.UNRESOLVED)
                + 0.3 * (regime != MacroRegime.UNKNOWN)
            ),
            2,
        )
        if self.policy.hard_no_trade_on_contested and scenario == Scenario.UNRESOLVED:
            reasons.append("RESULT_UNRESOLVED_OR_CONTESTED")
        if political_age > self.policy.political_staleness_hours:
            reasons.append("POLITICAL_DATA_STALE")
        if market_age > self.policy.market_staleness_minutes:
            reasons.append("MARKET_DATA_STALE")
        if regime == MacroRegime.UNKNOWN:
            reasons.append("CROSS_ASSET_CONFIRMATION_INSUFFICIENT")
        if surprise < self.policy.surprise_trade_threshold:
            reasons.append("SURPRISE_NOT_LARGE_ENOUGH")
        if regime == MacroRegime.MIXED:
            reasons.append("CROSS_ASSET_SIGNAL_MIXED")
        hard = {
            "RESULT_UNRESOLVED_OR_CONTESTED",
            "POLITICAL_DATA_STALE",
            "MARKET_DATA_STALE",
            "PREVIOUS_POLITICAL_PROBABILITY_INVALID",
            "CURRENT_POLITICAL_PROBABILITY_INVALID",
            "CROSS_ASSET_CONFIRMATION_INSUFFICIENT",
        }
        if any(reason in hard for reason in reasons):
            action = Action.NO_TRADE
        elif regime == MacroRegime.RISK_OFF and surprise >= self.policy.high_surprise_threshold:
            action = Action.HEDGE
        elif reasons:
            action = Action.WAIT
        else:
            action = Action.TRADE_CANDIDATE
        persistence = min(100.0, round(100.0 * event_half_life_hours(event_type) / 4320.0, 2))
        return EventDecision(
            action=action,
            scenario=scenario,
            macro_regime=regime,
            surprise_score=surprise,
            confidence_score=confidence,
            persistence_score=persistence,
            reasons=tuple(reasons),
            sector_view=sector_rotation(scenario, regime),
            relative_value=relative_value_candidates(scenario),
            political_age_hours=round(political_age, 2),
            market_age_minutes=round(market_age, 2),
            cross_asset=cross_asset_confirmation(market),
            political_risk_score=political_risk_score(
                surprise_score=surprise, scenario=scenario, regime=regime, contested=current.contested
            ),
            trade_expressions=trade_expression_candidates(
                scenario=scenario, regime=regime, surprise_score=surprise
            ),
            source_ids=tuple(sorted(set(previous.source_ids + current.source_ids))),
        )
