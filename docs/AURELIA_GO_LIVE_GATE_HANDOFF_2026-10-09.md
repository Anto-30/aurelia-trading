# AURELIA Go-Live Gate Handoff — 2026-10-09

## Current verified source

- Canonical repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Current engineering commit: `481d2610e9ac0c0a1b9b4209cfb94bd6c6aae373`
- Controlling live-release file: `config/LIVE_LOCK.yaml`
- Production deployment workflow: `.github/workflows/self-hosted-runtime-deploy.yml`
- Current live state: `live_trading_enabled=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`.

This file records the verified handoff and is not an authorization to move capital.

## Changes made and CI evidence

- Updated `.github/workflows/r100-prospective-oos.yml` to collect 600 seconds per scheduled run, schedule every 15 minutes, and set `cancel-in-progress: false`. Collection cadence changes do not alter the frozen strategy parameters or grant execution authority.
- The latest run for this commit reported these jobs successful: AURELIA Assurance, Free Runtime Worker, Agent Federation Audit, Agent Continuity Watchdog, and Secret Presence Report.
- On that successful assurance run, authenticated Deriv session verification and verify-only transaction lifecycle verification were skipped because `DERIV_AUTH_CONFIGURED=false`. A successful workflow with those steps skipped is not proof of authenticated access.
- The R100 collection run was still in progress when this handoff was recorded. The prior completed campaign report contained 101 total observations but 0 OOS observations, qualification `INSUFFICIENT_SAMPLE`, and production execution economics `UNDETERMINED_PRODUCTION`.
- The latest non-production 3,600-second soak was also still running when this handoff was recorded; do not count it as a completed production soak.
- No authenticated real-account session, production host deployment/health check, real order/fill lifecycle, or post-trade reconciliation was verified in this engineering session. No live order was submitted by this work.

## Required protected configuration

In GitHub repository Settings → Environments → `production` → Environment secrets, configure the appropriate Deriv bindings without putting secret values in chat, issue text, logs, or source control:

- `DERIV_AUTH_TOKEN` or `DERIV_PAT`
- `DERIV_EXPECTED_LOGINID` or `DERIV_AUTHORIZED_ACCOUNT_ID`
- `DERIV_EXPECTED_CURRENCY` (normally `USD`)
- `DERIV_AUTH_MODE` with the valid value `pat` or `oauth`
- `DERIV_APP_ID` is required when using PAT authentication; it is not required for OAuth.

A protected secret-presence report is not authentication. The verify-only workflows must run without skipped session/lifecycle steps and produce genuine current evidence tied to the correct real account, currency, and balance.

The current self-hosted deployment workflow separately requires an owner-controlled persistent Linux/Docker host and protected secrets:

- `AURELIA_HOST`
- `AURELIA_USER`
- `AURELIA_SSH_KEY`
- `AURELIA_KNOWN_HOSTS`

Strict SSH host verification must remain enabled. The connected engineering session currently has no remote Desktop Commander device, and no production-host handshake or health check has been observed. Railway is not the active deployment path.

## Strategy and model qualification gates

The current signal hunter labels its output `UNCALIBRATED_RESEARCH_ONLY`. That output is not a calibrated prediction, training result, or executable trade instruction. All AI agents and external repositories remain advisory/research/tooling sources; no agent may grant itself broker or capital authority.

Before strategy eligibility can pass, retain the existing frozen campaign and demonstrate, with source-bound evidence:

1. Complete prospective OOS collection after the campaign's predeclared OOS start, without retuning or reuse.
2. At least 100 valid OOS observations for the strategy/symbol/regime cell and positive OOS expectancy.
3. At least 100 observed quoted-contract economics samples with positive mean net return after actual quote-based payout, costs, and applicable execution assumptions.
4. Valid calibration under the existing reliability requirements, with no unresolved drift; probabilities outside the hard 0.55–0.75 range must be rejected rather than clipped.
5. A production deployment tied to the exact source commit, authenticated broker evidence, production soak, and signed/current attestations for market data, probability, Risk Warden, Execution Firewall, exposure, idempotency, watchdog, and reconciliation.
6. After any separately authorized live transaction, broker-confirmed transaction evidence and healthy reconciliation. Simulation, proposals, tests, and a green CI badge do not substitute for this evidence.

A $1 minimum contract must not override the deterministic risk budget. If the broker minimum stake makes risk disproportionate to the verified available balance, AURELIA must remain blocked rather than force a trade.

## Release rule

Keep the existing LIVE_LOCK, Risk Warden, Execution Firewall, account isolation, kill switch, idempotency, and reconciliation controls intact. Do not set `LIVE_EXECUTION=ENABLED`, alter LIVE_LOCK, or submit an order merely to make the release dashboard green. Release decisions must be made only after each genuine prerequisite is independently verified and the existing deterministic release gate passes.
