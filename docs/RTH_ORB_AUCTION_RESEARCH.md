# RTH ORB and Failed-Auction Research

## Decision
Continue research only. This package has no broker adapter and submits no orders.

## Critical review
OHLCV bars do not contain true volume-at-price. The provided profile method uniformly allocates each bar's volume across price bins and is explicitly approximate. Contract specifications and dated fees must be verified separately for NQ, ES, MNQ and MES. A completed close outside the opening range is a candidate signal, not a guaranteed fill. Sweep reversal requires independent structure/follow-through confirmation, stop/target geometry, and a conflict resolver before it can be an eligible strategy. Exchange holidays, early closes and point-in-time macro events require authoritative calendars; missing/stale calendar data must block entries.

## Implemented research scope
- Timezone-aware, complete, finite, OHLC-consistent bars; duplicate or unordered timestamps fail closed.
- Opening range uses bars in [09:30, 09:45) America/New_York, excluding the 09:45 bar.
- ORB close candidate requires a completed bar available by decision time, no earlier than 09:45 and no later than 15:30.
- Approximate profile is labelled as such.
- Integer contract sizing includes fees, slippage and spread allowance; zero contracts means NO TRADE.
- No broker calls, capital authority or live orders.

## Architecture target
Validated bars -> exchange calendar -> previous-session profile -> completed daily/hourly/15m context -> independent ORB and sweep strategies -> deterministic conflict resolver -> risk sizing -> event-driven fill simulator -> ledger reconciliation -> chronological validation/reporting. Any uncertain input returns INSUFFICIENT EVIDENCE or NO TRADE.

## Validation plan
Use chronological development/validation/locked OOS splits (initial 60/20/20) and walk-forward folds. Evaluate instruments and strategy modules independently, include baseline and 2x slippage stress, conservative ambiguous stop/target sequencing, confidence intervals accounting for serial dependence, and performance by direction/regime. Pre-register acceptance thresholds before inspecting final OOS. No backtest result is claimed here.

## Test status
Tests are authored in research/labs/tests/test_rth_orb_auction.py. This change does not execute them; treat status as NOT RUN until CI confirms. Tests for DST/holiday calendars, profile leakage, event blocking, fills, partial fills, daily loss, duplicate orders and ledger reconciliation remain outstanding.
