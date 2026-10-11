# RTH ORB and Failed-Auction Research

## Decision
Research only. This package has no broker adapter and submits no orders. It is separate from the Deriv synthetic-index execution path.

## Critical review
OHLCV bars do not contain true volume-at-price. The provided profile method uniformly allocates each bar volume across price bins and is explicitly approximate. Contract specifications and dated fees must be verified separately for NQ, ES, MNQ and MES. A completed close outside the opening range is a candidate signal, not a guaranteed fill. Sweep candidates require externally identified levels known before the bar and a completed close back across the level. The current conflict resolver rejects conflicting directions and also rejects simultaneous same-direction modules until precedence is validated. Exchange holidays, early closes and point-in-time macro events require authoritative calendars; missing/stale calendar data must block entries.

## Implemented research scope
- Timezone-aware, complete, finite, OHLC-consistent bars; duplicate or unordered timestamps fail closed.
- Opening range uses bars in [09:30, 09:45) America/New_York, excluding the 09:45 bar.
- ORB close candidate requires a completed bar available by decision time, no earlier than 09:45 and no later than 15:30.
- Approximate OHLCV profile is explicitly labelled and is not true volume-at-price.
- Integer contract sizing includes configured fees, slippage and spread allowance; zero contracts means NO TRADE.
- Candle integrity guard checks timestamps, completed bars, interval, order, duplicates, overlap and optional gaps; calendar guard blocks absent, stale, invalid or event-window snapshots.
- Sweep confirmation requires a previously known level, a completed candle, an excursion beyond that level and close-back-through confirmation.
- Conflict resolver fails closed for opposing or multiple active strategy candidates.
- No broker calls, capital authority or live orders.

## Architecture target
Validated bars -> authoritative exchange calendar -> previous-session profile -> completed daily/hourly/15m context -> independent ORB and sweep strategies -> deterministic conflict resolver -> risk sizing -> event-driven fill simulator -> ledger reconciliation -> chronological validation/reporting. Any uncertain input returns INSUFFICIENT EVIDENCE or NO TRADE.

## Validation plan
CI has confirmed the current research-lab test suite passes. This is unit-test evidence only, not evidence of strategy profitability or production readiness. Use chronological development/validation/locked OOS splits (initial 60/20/20) and walk-forward folds. Evaluate instruments and modules independently, include baseline and 2x slippage stress, conservative ambiguous stop/target sequencing, confidence intervals accounting for serial dependence, and performance by direction/regime. Pre-register acceptance thresholds before inspecting final OOS. No backtest result is claimed here.

## Remaining gaps
- Authoritative exchange holiday/early-close calendar and verified dated contract specifications/fees.
- Production point-in-time economic calendar and historical market data.
- Structure/follow-through confirmation, stop/target rules and event-driven fill simulation.
- Portfolio-level daily loss enforcement, order idempotency, complete ledger and reconciliation.
- Historical, walk-forward and locked OOS results; paper-trading soak and runtime evidence.
- No live orders or live execution qualification is implemented by this branch.
