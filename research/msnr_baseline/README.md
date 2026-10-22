# ATOS v2.0 — frozen MSNR research baseline

**Disposition: BLOCKED / VERIFY_ONLY. This is research-only code and cannot authorize a release.**

This directory contains a deterministic price-action MSNR baseline and unauthenticated historical-data pipeline. It has no account token/OTP authentication, account balance reads, proposal/buy/sell methods, or live-order route. Do not place this model in the production runtime.

## Model
The frozen parameters are in \`config/model_frozen.json\`: prior 20-bar sweep/reclaim, confirmation via 5-bar microstructure break within 8 completed bars, 200-SMA plus 20-bar SMA slope regime filter, ATR(14), 1-ATR stop, 2R target and 1% normalized equity risk. Chop blocks entries. Features are vectorized; signal and ATR from bar i-1 are used to decide an entry at the open of bar i. No price/indicator forward-fill is used. Execution runs in 90-day segments with a Numba kernel, a 250-row feature warm-up, JSONL append-only ledger, and memory cleanup. If stop and target can both be touched in one OHLC candle, stop is conservatively assumed first.

Only OHLC is used; HMM/LSTM, volume profile, order flow and retail oscillators are excluded. No strategy metric is valid until actual fetched history passes the verifier.

## Current Deriv API and data
The only endpoint used is \`wss://api.derivws.com/trading/v1/options/ws/public\`. Public \`active_symbols\` is matched using \`underlying_symbol\`; its \`pip_size\` is treated as a price-unit increment as shown in the active-symbol comparison. Do not conflate it with the similarly named display-precision field in tick/history responses. Candles must provide \`open\`, \`high\`, \`low\`, \`close\`, \`epoch\`. No legacy \`loginid\` or symbol request field is used.

Fetch command:
\`\`\`bash
python -m pip install -r requirements.txt
python scripts/fetch_history.py --output-dir data/raw
\`\`\`
Dates are inclusive UTC 2022-10-21 through 2024-10-21. Chunks are 3 days, paced by at least 1.5 seconds. Outputs are \`R_100_1m.csv\`, \`R_100_15m.csv\`, adjacent manifests, and the captured raw \`active_symbols\` response/hash. A failed run leaves a failure record and/or partial CSV; neither is eligible market data. Use a fresh output directory on retry.

Verify:
\`\`\`bash
python scripts/verify_history.py data/raw/R_100_1m.csv --manifest data/raw/R_100_1m.manifest.json --output data/raw/R_100_1m.verification.json
python scripts/verify_history.py data/raw/R_100_15m.csv --manifest data/raw/R_100_15m.manifest.json --output data/raw/R_100_15m.verification.json
\`\`\`
No interpolation, backfill or forward-fill is allowed. Simulator requires strictly contiguous full-period 1m history and an independent passing verification report.

## Simulator
Run only after authentic history has been fetched and verified:
\`\`\`bash
python scripts/run_msnr_simulator.py data/raw/R_100_1m.csv \
  --manifest data/raw/R_100_1m.manifest.json \
  --verification data/raw/R_100_1m.verification.json \
  --ledger evidence/run-01/trade_ledger.jsonl \
  --summary evidence/run-01/summary.json \
  --git-commit <EXACT_40_CHARACTER_GIT_COMMIT_SHA> \
  --allow-unverified-linear-proxy
\`\`\`
This branch may be used outside a Git clone, so supply the exact 40-character Git commit. The \`--allow-unverified-linear-proxy\` flag explicitly keeps output \`NOT_QUALIFIED\`: multiplier 1.0 is a unit-normalized linear price-PnL proxy, not evidence a real Deriv linear contract/multiplier is available. The user-specified spread of 2 pips is converted using the captured active-symbol increment; slippage is assumed at 5 bps per fill and both fills are approximated using entry price. Commission is excluded. Costs are assumed, not observed. No actual R_100 economics have been received due a DNS failure.

The simulator prints the three Holy Trinity values only on completion: CSV SHA-256, repository commit SHA and seed 42. Frozen kill rule: \`profit factor < 1.15 OR net expectancy <= 0 R\` prints exactly:
\`KILL CRITERIA MET: Baseline alpha insufficient. Halting HMM integration.\`
If no trade metrics are computable the kill rule is marked NOT EVALUATED. Do not tune parameters after viewing results.

## Verification status
See \`evidence/VALIDATION_RUNLOG.md\`, \`evidence/local_test_results.json\`, \`evidence/fetch_run.failure.json\`, and \`evidence/remote_tree_blob_manifest.json\`. Local code/control tests passed; the current public API host cannot be resolved in the available environment, so no market candles, manifests, trade ledger, profit factor, expectancy or kill-rule outcome exist.

Canonical \`config/LIVE_LOCK.yaml\` is not part of this branch and remains unchanged on main: \`LIVE_EXECUTION=BLOCKED\`, \`FINAL_EXECUTION_AUTHORIZATION=false\`, \`capital_plane_mode=VERIFY_ONLY\`.
