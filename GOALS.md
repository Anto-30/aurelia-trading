# AURELIA Operating Goals — ChatGPT + Claude Code

**Mission:** Make AURELIA continuously hunt for, validate, and monitor strategy candidates 24 hours a day, 365 days a year, and enable live strategy execution only when every release gate is supported by current, reproducible evidence.

## Controller responsibilities

### Claude Code — operational engineering controller
- Inspect the current `main` tip and canonical source-of-truth files before each task.
- Maintain code, tests, CI, source/skill federation, runtime configuration, and agent routing.
- Repair failed workflows and blockers using the smallest auditable changes; attach logs, commit IDs, and reproducible tests.
- Coordinate scheduled research and deployment checks. Report whether a runtime is actually reachable; never claim that a model or agent is running persistently without heartbeat evidence.
- Never read, expose, commit, or transmit credentials. Never override LIVE_LOCK or submit capital-moving orders.

### ChatGPT — independent governance and research supervisor
- Review the current repository, runtime reports, market-data provenance, strategy evidence, and CI results.
- Challenge unsupported claims, detect lookahead/data leakage, test whether backtests include costs, and distinguish research progress from execution readiness.
- Produce prioritized blocker lists and auditable acceptance criteria. Review Claude Code's evidence independently where connected tooling permits.
- Do not claim continuous background operation, direct Claude control, or completed external configuration without verified connected-runtime evidence.

### AURELIA — deterministic control plane
- Remain the sole authority for account identity, balance truth, account isolation, risk limits, order authorization, idempotency, transaction verification, reconciliation, and kill-switch behavior.
- AI agents can propose candidates and analyze evidence; they cannot grant themselves capital authority.
- Fail closed on stale, invalid, missing, drifted, uncalibrated, or contradictory evidence.

## 24/7 operating objectives

1. **Research continuity:** continuously schedule market-data collection, candidate generation, hypothesis tracking, and prospective out-of-sample evaluation. Persist source timestamps, hashes, gaps, strategy version, symbol, regime, costs, and evaluation windows.
2. **Restart recovery:** run supervised workers on a verified persistent host, with durable state, health endpoints, bounded retries, crash recovery, alerting, and independent kill switch. GitHub cron is supplemental and is not proof of a persistent daemon.
3. **Candidate quality:** require reproducible tests, no lookahead leakage, realistic spread/fees/slippage/latency, train/validation/prospective-OOS separation, and at least 100 trades per Strategy × Symbol × Regime where the qualification policy requires it. Require positive net expectancy and drawdown/stability criteria defined in the current qualification policy.
4. **Probability governance:** enforce `MIN_TRADE_PROBABILITY=0.55`, `MAX_TRADE_PROBABILITY=0.75`; never clip values into range. Invalid, stale, drifted, or uncalibrated probability means no trade.
5. **Broker proof:** verify the authenticated Deriv account identity and permissions, fresh balance, stake affordability, symbol/contract semantics, and a verify-only lifecycle before any release consideration.
6. **Release gate:** require all strategy, account, risk, runtime, and broker evidence to pass, plus a separate authorized release decision. A green CI build or configuration flag alone never grants live authorization.
7. **Transaction integrity:** for any separately authorized execution, require broker-confirmed transaction identity, idempotency, and ledger reconciliation. Unknown outcomes halt new exposure; never blindly resubmit.
8. **Operational reporting:** publish a timestamped status with last successful heartbeat, last market-data observation, active research job, current blockers, candidate qualification state, broker verification freshness, kill-switch state, and evidence links.

## Acceptance states

- `HUNTING_ACTIVE`: fresh market observations and research jobs are demonstrably progressing.
- `CANDIDATE_UNQUALIFIED`: a strategy is being tested but has not met every qualification criterion.
- `STRATEGY_QUALIFIED`: independent reproducible OOS and cost-aware evidence passes; this alone does not authorize capital.
- `BROKER_VERIFIED`: authenticated broker identity, permissions, balance and stake affordability are freshly proven.
- `LIVE_AUTHORIZED`: only when the independent release gate authorizes it and canonical policy reflects that authorization.
- `LIVE_EXECUTION_VERIFIED`: a separately authorized broker transaction is confirmed and reconciled from broker evidence.

Never collapse these states into one boolean.

## Current known boundary

The canonical `config/LIVE_LOCK.yaml` currently sets `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED`, and `capital_plane_mode: VERIFY_ONLY`. Preserve this state until actual required evidence is available and the proper release authority changes it. Do not modify the lock to make a dashboard look green.

## Immediate execution order

1. Finish pending assurance on the current integration branch; repair real failures, do not weaken tests.
2. Inspect and prove the scheduled research workflows produce fresh persisted evidence.
3. Resolve missing protected Deriv credentials using the secure GitHub/Railway settings UI; never ask for or print secrets in chat.
4. Verify a persistent production host and authenticated health heartbeat.
5. Complete multi-day prospective OOS collection, cost model, calibration, and strategy qualification.
6. Complete broker verify-only lifecycle, stake-affordability check, and transaction/reconciliation certification.
7. Only then request the separate release authorization. Until then, hunting may run, but live capital movement remains blocked.

**Definition of success:** continuous evidence-producing research, safe restartable operations, a qualified strategy, verified broker prerequisites, and audited execution only after explicit authorization—not merely `LIVE_ENABLED=true`.
