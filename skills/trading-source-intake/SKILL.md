---
name: trading-source-intake
description: Safely assess external trading bots, indicator libraries, and pattern detectors for AURELIA research without importing execution authority.
---
# Trading Source Intake

1. Pin the exact upstream commit and inspect repository age, license, dependency manifest/lockfile, CI, security advisories, API usage, and maintainer state.
2. Keep source browsing and tests isolated. Never place broker tokens, exchange keys, personal credentials, or production configuration in the checkout, notes, logs, or test fixtures.
3. Treat external bots as research-only. Do not run an external trading engine in parallel with AURELIA or connect it to live accounts.
4. For OHLC/candlestick libraries, test schema validity, monotonic timestamps, candle completeness, close-time semantics, pattern indexing, warm-up behavior, missing data, streaming parity, and lookahead leakage.
5. For indicator/signal projects, independently verify indicator formulas and source data. Account for spread, fees, slippage, latency, funding where applicable, and exchange-specific order semantics.
6. Require reproducible backtests, separate train/validation/OOS windows, strategy-symbol-regime evidence, calibration, and adequate sample size. A pattern match or a high in-sample win rate is not an edge qualification.
7. Compare extracted features against a simple baseline and ablation tests. Integrate only an isolated feature/adapter into AURELIA-owned research code after review; do not vendor a second order engine.
8. Keep Risk Warden, Execution Firewall, Balance Truth, Account Isolation, transaction verification, ledger reconciliation, and LIVE_LOCK sovereign. External agents and tools have no capital authority.
9. Record the actual status precisely: `PINNED`, `REVIEWED`, `TESTED`, `INTEGRATED`, or `NOT_INSTALLED`. Do not conflate them.
