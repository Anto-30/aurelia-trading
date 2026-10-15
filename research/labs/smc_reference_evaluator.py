"""Conservative OHLC reference-outcome evaluation for SMC research.

These outcomes are price-path proxies. They do not represent broker fills,
contract P&L, executable stops/limits, or net returns. Unknown transaction
costs and instrument-specific payoff mapping block economic qualification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Sequence

from research.labs.smc_trend_agent import (
    OHLCBar,
    ResearchSetup,
    _utc,
    validate_bars,
)


OutcomeStatus = Literal[
    "INVALIDATED_BEFORE_ENTRY",
    "TARGET_PASSED_BEFORE_ENTRY",
    "STOP_TOUCHED_BEFORE_ENTRY",
    "ENTRY_NOT_TOUCHED",
    "PENDING_AT_DATA_END",
    "AMBIGUOUS_ENTRY_BAR",
    "STOP_REFERENCE",
    "TARGET_REFERENCE",
    "OPEN_AT_DATA_END",
]


@dataclass(frozen=True)
class ReferenceOutcome:
    strategy_id: str
    strategy_version: str
    symbol: str
    direction: str
    signal_timestamp_utc: str
    status: OutcomeStatus
    elapsed_bars: int
    entry_reference_touched: bool
    gross_reference_r: float | None
    ambiguous_path: bool
    resolution_rule: str
    cost_status: str = "UNKNOWN"
    net_reference_r: float | None = None
    qualification_status: str = "BLOCKED_COSTS_UNKNOWN_AND_CONTRACT_MAPPING_UNVERIFIED"
    capital_authority: bool = False
    order_submission_permitted: bool = False

    def as_payload(self) -> dict[str, object]:
        return asdict(self)


def evaluate_reference_outcome(
    setup: ResearchSetup,
    subsequent_bars: Sequence[OHLCBar],
) -> ReferenceOutcome:
    """Evaluate the reference levels using only bars after the signal close.

    For an established reference entry, a bar touching both stop and target is
    resolved stop-first (pessimistic). If target is also crossed on the initial
    entry-touch bar and the stop is not crossed, intrabar order is unknowable;
    that case is marked ambiguous and receives no R value. A stop touched on
    the entry bar is counted as -1R conservatively. Price touching the entry
    reference is never asserted to be a real fill.
    """
    validate_bars(subsequent_bars)
    signal_time = _utc(setup.signal_timestamp_utc)
    for bar in subsequent_bars:
        if _utc(bar.timestamp_utc) <= signal_time:
            raise ValueError("FOLLOW_UP_BAR_NOT_AFTER_SIGNAL")

    direction = setup.direction
    long_side = direction == "LONG"
    entry = setup.entry_limit_reference
    stop = setup.stop_reference
    target = setup.target_reference
    entered_by_reference_touch = False

    def make(
        status: OutcomeStatus,
        elapsed: int,
        *,
        touched: bool = False,
        gross_r: float | None = None,
        ambiguous: bool = False,
        rule: str,
    ) -> ReferenceOutcome:
        return ReferenceOutcome(
            strategy_id=setup.strategy_id,
            strategy_version=setup.strategy_version,
            symbol=setup.symbol,
            direction=direction,
            signal_timestamp_utc=setup.signal_timestamp_utc,
            status=status,
            elapsed_bars=elapsed,
            entry_reference_touched=touched,
            gross_reference_r=gross_r,
            ambiguous_path=ambiguous,
            resolution_rule=rule,
        )

    for elapsed, bar in enumerate(subsequent_bars, start=1):
        invalidated = (
            bar.close < setup.order_block_low
            if long_side
            else bar.close > setup.order_block_high
        )
        if not entered_by_reference_touch:
            if invalidated:
                return make(
                    "INVALIDATED_BEFORE_ENTRY", elapsed,
                    rule="CLOSE_BEYOND_ORDER_BLOCK_PRECEDES_ENTRY",
                )

            entry_touched = bar.low <= entry <= bar.high
            stop_touched = bar.low <= stop if long_side else bar.high >= stop
            target_touched = bar.high >= target if long_side else bar.low <= target

            if not entry_touched:
                if target_touched:
                    return make(
                        "TARGET_PASSED_BEFORE_ENTRY", elapsed,
                        rule="TARGET_REFERENCE_TOUCHED_WITHOUT_ENTRY_REFERENCE",
                    )
                if stop_touched:
                    return make(
                        "STOP_TOUCHED_BEFORE_ENTRY", elapsed,
                        rule="STOP_REFERENCE_TOUCHED_WITHOUT_ENTRY_REFERENCE",
                    )
                if elapsed >= setup.expires_after_bars:
                    return make(
                        "ENTRY_NOT_TOUCHED", elapsed,
                        rule="PENDING_SETUP_EXPIRED_WITHOUT_ENTRY_TOUCH",
                    )
                continue

            if stop_touched:
                return make(
                    "STOP_REFERENCE", elapsed,
                    touched=True, gross_r=-1.0, ambiguous=True,
                    rule="STOP_FIRST_CONSERVATIVE_ENTRY_BAR",
                )
            if target_touched:
                return make(
                    "AMBIGUOUS_ENTRY_BAR", elapsed,
                    touched=True, ambiguous=True,
                    rule="TARGET_AND_ENTRY_IN_SAME_OHLC_BAR_ORDER_UNKNOWN",
                )
            entered_by_reference_touch = True
            continue

        stop_touched = bar.low <= stop if long_side else bar.high >= stop
        target_touched = bar.high >= target if long_side else bar.low <= target
        if stop_touched and target_touched:
            return make(
                "STOP_REFERENCE", elapsed,
                touched=True, gross_r=-1.0, ambiguous=True,
                rule="STOP_FIRST_CONSERVATIVE_SAME_BAR_EXIT",
            )
        if stop_touched:
            return make(
                "STOP_REFERENCE", elapsed,
                touched=True, gross_r=-1.0,
                rule="STOP_REFERENCE_TOUCHED",
            )
        if target_touched:
            return make(
                "TARGET_REFERENCE", elapsed,
                touched=True, gross_r=setup.target_multiple_r,
                rule="TARGET_REFERENCE_TOUCHED",
            )

    if entered_by_reference_touch:
        return make(
            "OPEN_AT_DATA_END", len(subsequent_bars),
            touched=True,
            rule="NO_STOP_OR_TARGET_REFERENCE_OBSERVED_BEFORE_DATA_END",
        )
    return make(
        "PENDING_AT_DATA_END", len(subsequent_bars),
        rule="INSUFFICIENT_FOLLOW_UP_BARS_TO_RESOLVE_PENDING_SETUP",
    )
