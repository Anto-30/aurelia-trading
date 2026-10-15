# Event-driven MSNR backtester — research-only

## Purpose
This module provides a deterministic OHLC replay kernel for strategy hypotheses such as MSNR plus Volume Profile context. It does not define MSNR signals, ingest Deriv data, make strategy claims, or submit orders. The signal generator must be tested separately for prefix stability and point-in-time correctness.

## Execution contract
- A signal is timestamped by the index of the candle whose close made the signal knowable.
- The earliest entry is the next candle's open. The signal candle's close is never used as an executable fill.
- OHLC prices are treated as mid prices; configured spread (split half at each side), adverse per-fill slippage, and round-trip per-unit commission are applied.
- A position is held one at a time. Signals while a position is open are explicitly recorded as skipped.
- If stop and target are both touched within one candle, the stop is selected conservatively because OHLC does not reveal intrabar ordering. Gaps through a stop use the worse opening price.
- Signals outside the configured probability interval are rejected, not clipped. Defaults follow the AURELIA policy (0.55–0.75); calibration is not implied by passing this range.
- Remaining positions are marked out at the last close with exit costs. The report is not a broker ledger or account-equity reconciliation.

## Metrics
Returns per-unit net PnL, the sum of positive trade PnLs, the absolute sum of negative trade PnLs, profit factor, win rate, expectancy, and peak-to-trough drawdown on the closed-trade equity curve. Drawdown is not marked-to-market intratrade drawdown. Since no account sizing, contract payout, financing, margin, latency, rejected-order, or broker reconciliation model is included, these are screening metrics only.

## Required validation before any strategy conclusions
1. Add independent hand-calculated parity fixtures and randomized/property tests.
2. Demonstrate prefix stability: adding future candles cannot change past signal features or past trades.
3. Freeze strategy rules and profile parameters before out-of-sample evaluation; use walk-forward splits and sensitivity analysis.
4. Model the actual instrument's payout/contract semantics and broker costs. This generic price-difference kernel is not valid for Deriv contracts unless a separate verified adapter translates contract economics correctly.
5. Validate source coverage, timestamp units, duplicates, gaps, session boundaries, spread/slippage distributions, and latency assumptions.
6. Report sample size, uncertainty, drawdown, profit factor, expectancy, exposure, and cost stress tests. Do not optimize on the final holdout.
7. Keep the existing LIVE_LOCK, Layer 6 vetoes, broker verification, independent human review, soak, and release gates unchanged.

## Non-goals and safety
Research-only status is enforced by project location and documentation, not by a claim that tests authorize deployment. This module has no API client, credentials, network transport, runtime registration, or capital authority.
