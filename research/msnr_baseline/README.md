# ATOS v2.0 — R_100 MSNR validation (research-only)

**Current disposition: BLOCKED / VERIFY_ONLY. No empirical alpha result exists.**

This directory holds an isolated, frozen price-action MSNR baseline, public history fetcher/verifier, public-only data client, and independent cost/performance ledger. It is not a production execution engine. It must not be merged as strategy qualification or release authorization.

## Current Deriv public API

The history fetcher uses only the unauthenticated endpoint wss://api.derivws.com/trading/v1/options/ws/public. It captures active-symbol metadata, then requests 1m and 15m OHLC candles in chunks capped at 900 candles and at most 3 days, with at least 1.5-second pacing, over the exact half-open UTC window [2022-10-21T00:00:00Z, 2024-10-21T00:00:00Z). The 1m span is therefore at most 15 hours per request, while the 15m span is at most 3 days. This stays below the current API's default count of 1000 while avoiding the observed gateway behavior when an explicit count is paired with bounded start/end. See https://developers.deriv.com/docs/data/ticks-history/. The --end-date argument is an exclusive midnight boundary; no bars from the end date are included. Every candle requires open, high, low, and close plus an epoch; any source candle outside the exact requested chunk is rejected, even if all expected in-window bars are also present. The request operation remains ticks_history, with the symbol as its value; underlying_symbol is used where the current schema requires that field. The official current schema has an explicit candle-granularity enum and permits subscribe/adjust_start_time only as integer 1 if supplied. This one-shot fetcher omits both flags rather than sending legacy 0 values. No loginid or credential is used.

Commands:

    python -m pip install -r requirements.txt
    python scripts/fetch_history.py --start-date 2022-10-21 --end-date 2024-10-21 --output-dir data/raw
    python scripts/verify_history.py data/raw/R_100_1m.csv --manifest data/raw/R_100_1m.manifest.json --output data/raw/R_100_1m.verification.json
    python scripts/verify_history.py data/raw/R_100_15m.csv --manifest data/raw/R_100_15m.manifest.json --output data/raw/R_100_15m.verification.json

The source manifest uses schema v3 and records start_date_utc_inclusive plus end_date_utc_exclusive; the verifier rejects legacy inclusive-end manifests rather than silently changing their meaning.

No interpolation, backfill, forward-fill, or silent dropping of extra/out-of-window candles is allowed. Any missing bars, extra bars, checksum mismatch or failed source verification blocks simulation. Partial CSV files and failure records are not valid data.

## Frozen MSNR baseline

The frozen configuration in config/model_frozen.json defines a price-action sweep/reclaim, 5-bar microstructure break, 200-period simple moving-average regime with slope, ATR(14), a 1-ATR stop, 2R target and 1% normalized equity risk. The features are vectorized. Signal and ATR from bar i-1 may trigger entry only at bar i's open. Chop blocks entries. No HMM/LSTM, volume profile, order-flow or retail oscillators are included.

The stateful simulation uses a Numba-compiled loop across 90-day segments, a 250-row feature warm-up, append-only JSONL trade ledger, and explicit memory cleanup. The final bar closes any remaining position. The simulator requires genuine history, a matching SHA-256 manifest and a passing continuity report.

Run only after verification succeeds:

    python scripts/run_msnr_simulator.py data/raw/R_100_1m.csv --manifest data/raw/R_100_1m.manifest.json --verification data/raw/R_100_1m.verification.json --ledger evidence/run-01/trade_ledger.jsonl --summary evidence/run-01/summary.json --git-commit EXACT_40_CHARACTER_GIT_COMMIT_SHA --allow-unverified-linear-proxy

The linear-proxy flag means results remain NOT_QUALIFIED: multiplier 1.0 is normalized price-PnL, not an independently verified Deriv contract multiplier. Spread 2.0 pips and slippage 5 bps per fill are assumptions, not observations; commission is excluded. The Holy Trinity values (CSV SHA-256, exact repository commit, seed 42) are printed only after a data-backed run completes.

Fixed kill rule: profit factor below 1.15 OR net expectancy at or below 0R prints exactly: KILL CRITERIA MET: Baseline alpha insufficient. Halting HMM integration. If verified data or computable metrics are absent, the kill rule is NOT EVALUATED, not passed or failed.

## Public data client and separate performance ledger

scripts/deriv_public_market_data.py is pinned to the public endpoint and supports only active_symbols, ticks_history and ticks. It rejects auth/account/trading request keys and nested equivalents; it has no PAT, OTP, account/balance, proposal, buy or sell route. Public tick reconnect behavior never requests OTP because it has no authenticated session.

scripts/performance_ledger.py is a separate tool for raw, pre-cost trades with entry_time, exit_time, entry_price, exit_price, direction, size and initial_risk. It requires explicit commission, spread, pip increment, slippage, multiplier and starting equity. It computes gross/net PnL, cost breakdown, R-multiples, net profit factor, expectancy, win rate and trade-close drawdown. It rejects fields suggesting the input is already costed, to avoid double charging. Do not pass the MSNR simulator's JSONL ledger to this second cost engine; the simulator ledger already deducts its configured costs.

## Third-party repository intake

docs/REPOSITORY_INTAKE.md triages all ten additional GitHub repositories supplied for review. No repository is approved for wholesale vendoring into the canonical trading runtime. FastAPI aligns with the current Python direction; most other projects are deferred, incompatible, optional sidecars, or require licensing/security review.

## Verification evidence

The research test suite passed 17 tests and the full exported bundle passed 27 structural tests. Python compilation and CLI help checks passed. These results do not constitute empirical trading evidence.

The latest fetch failed before receiving any API response because DNS could not resolve api.derivws.com. See evidence/CONTINUATION_20261022.md and evidence/fetch_attempt_20261022_repo_intake/fetch_run.failure.json. There are currently no verified 1m/15m CSVs, manifests, simulator ledger, profit factor, expectancy, drawdown or evaluated kill rule. The 3,600-second soak and independent review remain incomplete.

Canonical config/LIVE_LOCK.yaml is not present in this research branch and has not been modified. Main remains LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false and capital_plane_mode=VERIFY_ONLY.
