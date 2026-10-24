# OOS evidence and soak runbook

This runbook separates **data capture**, **strategy evaluation**, **transport soak**, and **release authorization**. A successful step never implies that the next step passed.

## 1. Public Deriv candle capture and OOS scoring

The public Deriv market-data WebSocket accepts historical-candle requests without account authorization. Only the numeric app ID is needed for the read-only market-data runners; do not put a demo or real-account token on the command line or into this script's environment.

From the repository root:

```bash
export DERIV_APP_ID=1089
python scripts/run_oos_validation.py --oos-months 3 --granularity 60 --out-dir artifacts/oos
```

The script fetches exact interval coverage, checks OHLC/timestamps, writes a CSV plus companion SHA-256 manifest, and records the running code commit. It deliberately exits with `OOS_METRICS=NOT_COMPUTED` (exit code 3) if the matched four-model trade ledger and hash-bound cost source are absent. That is **not** a successful strategy validation; it is an explicit incomplete state.

The canonical research protocol reserves the newest three **calendar months**. The default `--oos-months 3` computes calendar-month boundaries; `--oos-months 2` does not satisfy the final-OOS protocol. A fixed-day `--oos-days 30` window is exploratory only, regardless of its length. A date range and hash alone also cannot prove that the data was unseen during model selection; freeze the model/config/code choices before the final evaluation and document the freeze commit.

### Required evaluator inputs

The current `research/atos_validation/four_model_backtest.py` evaluator scores an audited ledger; it does not generate strategy trades. The ledger must be produced by the real, frozen strategy simulator and contain these columns:

- `timestamp`: ISO-8601 timestamp with explicit timezone.
- `strategy`: exactly `alpha_beta_hmm`, `gaussian_hmm`, `ma_control`, or `unfiltered_msnr`.
- `r_gross`: trade outcome before costs, in R.
- `cost_r`: nonnegative per-trade cost in R derived by the named cost model.
- `fold`: shared walk-forward fold ID; all four models need matching folds.

The cost-evidence JSON must use schema `aurelia.execution_economics_evidence.v1` and bind all of the following to the same run: `symbol`, `oos_start_epoch`, `oos_end_epoch`, `data_sha256`, `trade_ledger_sha256`, `cost_basis`, `cost_source_file`, `cost_source_sha256`, `cost_method`, and `independent_review_status`. The cost source file is resolved relative to the JSON file unless an absolute path is supplied. The runner verifies hashes and linkage; it cannot authenticate the origin of a quote file or establish that a cost model is economically realistic. Independent review of Deriv contract semantics, payout/settlement, and cost assumptions is still required.

Once the trade generator and cost source exist, rerun:

```bash
python scripts/run_oos_validation.py \
  --oos-months 3 \
  --granularity 60 \
  --out-dir artifacts/oos \
  --trades-csv artifacts/oos/four_model_oos_trades.csv \
  --cost-evidence artifacts/oos/execution_cost_evidence.json
```

The resulting report includes the dataset and ledger hashes, aggregate and per-fold metrics, and descriptive IID-normal confidence intervals. Those intervals do not correct for serial dependence, overlapping trades or multiple testing. The report always leaves live authorization false.

## 2. Non-production public-tick soak

Run the script on the host whose connection and runtime are being tested:

```bash
export DERIV_APP_ID=1089
python scripts/run_soak_test.py --duration-seconds 3600 --out-dir artifacts/soak
```

It subscribes to public R_100 ticks without account authorization, records WebSocket ping round-trip time separately from local research-signal processing time, logs automatic connection/reconnection events, and writes a raw JSONL log plus summary JSON. It has no order submission path.

A shorter run is only a smoke test and cannot qualify as the 3,600-second evidence. Ping RTT is not one-way market-feed latency and cannot alone establish scalping viability. This script does not deliberately toggle the host network, authenticate an account, test rejected orders, or prove strategy edge. Run the manual 10-second disconnect/reconnect test separately and retain the corresponding timestamped evidence.

Do **not** call a live `buy` or `sell` endpoint to check whether a read-only token is rejected. Verify scopes/account permissions using non-trading inspection or a controlled mock; a misconfigured token could make an endpoint probe an actual order.

## 3. Secrets, artifacts and release state

- `.env` and `.env.*` are ignored by the repository. Do not commit tokens, cookies, OTPs, private URLs, or account statements.
- Public history/tick capture does not require `DERIV_DEMO_TOKEN`. Authenticated read-only account checks use the separate protected, manual verification workflow.
- Keep raw logs and downloaded CSVs under ignored `artifacts/` locally. Upload only sanitized summaries after checking for account identifiers, balances, order IDs, tokens, and private connection details.
- Record the exact code commit, data manifest hash, trade-ledger hash, cost-source hash, and actual elapsed soak duration. Never replace missing evidence with a placeholder or simulated success.

Current final disposition remains `VERIFY_ONLY`, `LIVE_EXECUTION=BLOCKED`, and `FINAL_EXECUTION_AUTHORIZATION=false`. Green CI means code checks passed, not that data capture, OOS economics, authenticated broker verification, soak/recovery, or independent release review is complete.
