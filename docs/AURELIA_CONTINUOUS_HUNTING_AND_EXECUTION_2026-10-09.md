# AURELIA Continuous Hunting and Strategy Execution — Operating Contract

## Goal and accurate operating semantics

AURELIA should continuously hunt for candidate strategies, collect prospective observations, test hypotheses, evaluate calibration and costs, and promote only candidates with reproducible out-of-sample evidence. “Continuous” means scheduled collection and supervised long-running runtime where available; GitHub cron alone is not an always-on daemon and is not a guarantee that jobs start exactly on schedule.

## Controller split

- **Claude Code — operational engineering controller:** codebase, CI, agent routing, workflow repair, deployment evidence, and controlled orchestration. It must not self-authorize trades.
- **ChatGPT — governance and analysis supervisor:** methodology, blocker analysis, independent review, and release-gate scrutiny. This chat does not persistently run in the background or directly control Claude Code without a separately connected runtime.
- **AURELIA deterministic control plane — final authority:** the only component that may evaluate whether capital movement is authorized. External agents, plugins, repositories, and research workers have no capital authority.

The exact machine-readable contract is in `config/continuous_operations.json`.

## Existing periodic automation

- Control heartbeat: every 5 minutes.
- Agent continuity watchdog: every 15 minutes.
- Prospective public R100 research collection: every 15 minutes.
- Free runtime probe: every 15 minutes.
- Deriv verify-only evidence workflow: every 6 hours, dependent on protected credentials being configured.

These workflows support continuous research and health checks, but they do not establish that a single persistent process is running 24/7. GitHub Actions scheduling is best-effort, may be delayed, and should not be used as the sole execution venue for a latency-sensitive live trading daemon.

## Strategy promotion pipeline

1. Collect immutable, timestamped market data and record data provenance, gaps, source hashes, and market conditions.
2. Define a hypothesis before evaluation; version the strategy specification and implementation independently.
3. Run deterministic tests for candle semantics, lookahead leakage, missing data, costs, slippage, and order assumptions.
4. Use separated development, validation, and genuinely prospective out-of-sample periods. Never reuse tuning observations as independent OOS evidence.
5. Evaluate strategy × symbol × regime with the required sample size, positive net expectancy, drawdown limits, stability, calibration, and probability policy. A pattern detector or high in-sample win rate is not qualification.
6. Run shadow/paper mode, then authenticated verify-only broker lifecycle and reconciliation.
7. Require a separate, explicit release authorization for capital. Any unknown broker outcome halts new exposure and triggers reconciliation; never blindly resubmit.

## Current release boundary

`LIVE_LOCK` remains authoritative: `live_trading_enabled=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `LIVE_EXECUTION=BLOCKED`. This is not a code defect to remove; it reflects missing or unproven release evidence. In particular, do not declare live readiness based on public market data, a green CI workflow, a configured secret name, or an `LIVE_ENABLED` flag alone.

## Production hosting requirement

For genuine continuous execution, deploy a persistent worker to a supported always-on host with authenticated health heartbeats, supervised restarts, durable state, idempotent order handling, independent kill switch, monitoring, and tested recovery. The host must be verified directly. A periodic GitHub workflow is useful for research and audit, but it is not a substitute for that host.

## Success criteria

- Fresh market observations continue to be collected and persisted.
- Strategy candidates carry provenance and immutable version identifiers.
- Each qualification claim links to reproducible tests and genuinely prospective OOS evidence.
- A failed/stale data source stops new strategy decisions.
- Authenticated broker account identity and balance are freshly verified.
- Every broker transaction is confirmed and reconciled exactly once.
- Risk controls remain deterministic and independent from AI recommendations.
- Live execution remains blocked until every required gate is evidenced and authorized.
