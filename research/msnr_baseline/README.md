# ATOS v2.0 — MSNR baseline (research-only)

This is an isolated research implementation. It never places orders and must not use authenticated endpoints. Canonical `config/LIVE_LOCK.yaml` is untouched.

## Data
Install `requirements.txt`, then run `python research/msnr_baseline/scripts/fetch_history.py --out-dir data/raw`. It uses only `wss://api.derivws.com/trading/v1/options/ws/public`, requests R_100 candles in 3-day chunks, validates OHLC fields, writes CSVs and SHA-256 manifests, and reports gaps over 120 seconds. Network failures abort; no synthetic fallback exists.

## Baseline
Frozen MSNR: sweep/reclaim of prior 20-bar structure, MA200 regime gate (chop blocks), ATR(14), 1.5 ATR stop, 2 ATR target. Features are vectorized before the stateful simulation; decisions use the previous completed candle and enter at the next open. No `ffill`. Process in three-month chunks and append trades to JSONL.

## Fail-closed instrument economics
`config/instrument_specs.json` intentionally has null tick/pip size, multiplier and equity. The simulator refuses to run until these are filled from independently verified linear-contract economics and `independently_verified=true`. The 2-pip spread and 5-bps slippage assumptions do not establish how pips map to R_100 prices. Binary options are forbidden.

The simulator prints data SHA-256, caller-supplied exact repository commit SHA, and seed 42. Pass the actual checkout commit with `--commit-sha`. No empirical result is claimed until verified data and economics exist.
