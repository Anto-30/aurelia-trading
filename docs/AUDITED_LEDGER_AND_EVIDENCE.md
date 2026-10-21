# AURELIA history, audit ledger, and release evidence guide

All commands are research/verification only. They do not submit orders or change config/LIVE_LOCK.yaml.

## 1. Fetch and seal the historical data

Use a numeric Deriv application ID, not an account token. Public market-history requests require no account token. The downloader requests at most 4,500 candles per page (never more than 5,000), pauses at least one second between pages, and rejects invalid OHLC, duplicate bars, missing intervals, and incomplete coverage. Synthetic-index volume remains null because it is not provided as conventional traded volume.

Run separately for 1-minute and 15-minute candles, using UTC boundaries aligned to the timeframe:

    export DERIV_APP_ID='<numeric application ID>'
    python scripts/fetch_deriv_history.py --symbol R_100 --start 2024-10-21T00:00:00Z --end 2026-10-21T00:00:00Z --granularity 60 --bars-per-request 4500 --out data/deriv/R_100_1m.csv
    python scripts/verify_deriv_history_manifest.py data/deriv/R_100_1m.csv

    python scripts/fetch_deriv_history.py --symbol R_100 --start 2024-10-21T00:00:00Z --end 2026-10-21T00:00:00Z --granularity 900 --bars-per-request 4500 --out data/deriv/R_100_15m.csv
    python scripts/verify_deriv_history_manifest.py data/deriv/R_100_15m.csv

These dates illustrate a 24-month request ending on 21 October 2026; confirm the real returned coverage. Each CSV has its own JSON manifest, row count, exact UTC interval, CSV SHA-256, and manifest SHA-256. Keep the CSV and manifest together and read-only after capture. Independently anchor each resulting digest in the release issue. A hash proves consistency after the digest is anchored; it does not prove that the dataset was complete or honest before hashing.

The 15-minute file is a separate artifact. Preserve its hash and timestamps. Any 15-minute feature used for a 1-minute decision must be aligned causally so a later 15-minute close cannot leak into an earlier 1-minute signal.

## 2. Record every decision and closed trade

The module research/atos_validation/audited_ledger.py supplies AuditedLedgerWriter. It does not generate signals, simulate fills, infer payouts, or submit orders. Integrate it into the frozen simulator: call record_decision for every candidate, including rejected and no-trade decisions; call record_trade only for a simulated trade that actually closes.

The writer requires the signal candle timestamp and the next candle boundary for entry, logs HMM regime state, entry/exit timestamps and prices, spread/slippage/commission cost inputs, cash P&L, gross R, cost R, net R, symbol, model/config hash, fold ID, and data hash. Every JSONL event is chained to the prior event hash; the manifest records the final file hash. It refuses to overwrite existing outputs and will not seal while an accepted entry is missing its closed-trade record.

The simulator must calculate actual gross P&L and each cost using its real replay inputs. Do not pass synthetic or guessed spreads, slippage, or payouts. Use the same ledger file for multiple strategies/folds, with each strategy's own model_config_sha256.

Verify the finished ledger and companion manifest:

    python -m research.atos_validation.audited_ledger artifacts/trades/audited_trades.jsonl

The final file hash detects later byte-level changes, and the record chain detects edits/deletions within the log. Neither can prove that the simulator omitted a decision before logging it. Reconcile source bars, signal counts, rejected decisions, trade closes and simulator output independently.

## 3. Generate the nine evidence files

The scripts/build_release_evidence.py program consumes real source artifacts, verifies the history manifest against its CSV and verifies the chained ledger plus its manifest. It derives trade metrics only when the relevant data exists. Missing or uncomputable metrics are emitted as JSON null; field-level explanations are written to evidence/evidence_notes.md because JSON does not support comments. Any null means incomplete evidence, never a pass.

Provide actual paths for broker lifecycle and recovery reports, soak summary, calibration report, cost-evidence JSON, security audit report, deployment/CI report, and WFA fold metrics. Example command structure:

    python scripts/build_release_evidence.py --evidence-dir evidence --history-manifest data/deriv/R_100_1m.csv.manifest.json --data-path data/deriv/R_100_1m.csv --ledger artifacts/trades/audited_trades.jsonl --oos-strategy alpha_beta_hmm --oos-start-date 2027-01-21 --oos-end-date 2027-04-21 --model-freeze-utc 'timestamp from the independently anchored freeze record' --broker-lifecycle-json artifacts/runtime/broker_lifecycle.json --recovery-json artifacts/runtime/recovery_matrix.json --soak-summary artifacts/soak/actual_run.summary.json --calibration-json artifacts/research/calibration.json --cost-evidence-json artifacts/research/execution_cost_evidence.json --security-audit-json artifacts/security/security_audit.json --deployment-json artifacts/deployment/deployment.json --wfa-fold-metrics artifacts/research/four_model_fold_metrics.csv

Only use an actual model/config freeze timestamp that precedes the OOS start. The example OOS interval is a prospective target, not existing data or a claim that the test has happened. After freezing code/config/thresholds, the prospective interval must elapse, then be evaluated once. If you have no measured starting equity, omit that option; drawdown and Sharpe will stay null rather than pretending that R drawdown is account-equity drawdown.

Outputs are broker_lifecycle.json, recovery_matrix.json, soak_3600s.json, prospective_oos.json, calibration.json, execution_economics.json, security_audit.json, deployment.json, and strategy_eligibility.json. Existing outputs are not overwritten unless --overwrite is explicitly supplied. Archive and externally anchor prior hashes before overwriting. The generator keeps eligible_for_live_unlock false unconditionally.

## 4. Attach generated hashes to Issue #185

After running on the authorized local or staging host, attach the actual CSV and manifest hashes, ledger and manifest hashes, code commit, model/config bundle hash, OOS interval and freeze time, raw soak log hash and actual elapsed duration, plus SHA-256 hashes for the nine JSON files to Issue #185. Do not include tokens, cookies, account identifiers, or unredacted logs. The repository-connected session cannot attach real artifact hashes until local data and runtime logs have actually been generated and supplied.

Keep config/LIVE_LOCK.yaml unchanged. Do not probe token permissions with a live buy/sell call; use non-trading scope metadata or a controlled mock. Green CI, public market data, and hash creation are not proof of strategy edge, account authentication, recovery, or release readiness.
