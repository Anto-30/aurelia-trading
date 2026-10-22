# ATOS v2.0 — R_100 MSNR validation (research-only)

**Current disposition: BLOCKED / VERIFY_ONLY. No empirical alpha result exists.**

This directory holds an isolated, frozen price-action MSNR baseline, public history fetcher/verifier, public-only data client, and independent cost/performance ledger. It is not a production execution engine. It must not be merged as strategy qualification or release authorization.

## Current Deriv public API

The history fetcher uses only the unauthenticated endpoint wss://api.derivws.com/trading/v1/options/ws/public. It captures active-symbol metadata, then requests 1m and 15m OHLC candles in 3-day chunks with at least 1.5-second pacing for inclusive UTC dates 2022-10-21 through 2024-10-21. Every candle requires open, high, low, close and epoch; current history responses require prices and times arrays. The request field for history remains ticks_history with the symbol as its string value; underlying_symbol is used for current active-symbol metadata and where the new API schemas specify that field. The current comparison permits subscribe and adjust_start_time values 0 or 1, and removes the legacy fixed granularity enum; this client omits subscribe for one-shot requests and validates positive integer granularity. No loginid or credential is used.

Commands:

    python -m pip install -r requirements.txt
    python scripts/fetch_history.py --start-date 2022-10-21 --end-date 2024-10-21 --output-dir data/raw
    python scripts/verify_history.py data/raw/R_100_1m.csv --manifest data/raw/R_100_1m.manifest.json --output data/raw/R_100_1m.verification.json
    python scripts/verify_history.py data/raw/R_100_15m.csv --manifest data/raw/R_100_15m.manifest.json --output data/raw/R_100_15m.verification.json

No interpolation, backfill or forward-fill is allowed. Any missing bars, checksum mismatch or failed source verification blocks simulation. Partial CSV files and failure records are not valid data.

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
