# AURELIA Current Operational State — 2026-10-07

## Source of truth

- Repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Latest observed main tip: `f35ad10ed0be01fcf6aed273bb507201e387cd7e`
- Live-release control: `config/LIVE_LOCK.yaml`
- Intelligence routing: `config/intelligence_source_routing.json`
- Intelligence routing assurance: `assurance/test_intelligence_source_routing.py`

## Latest engineering changes

The latest main-branch work strengthens the existing research and release boundary rather than creating a second trading engine.

Recent changes include:
- R100 economics qualification now requires quoted execution economics and the precedence bug in that gate has been corrected.
- Prospective R100 campaigns now close/roll safely, settle pending observations, and preserve immutable source provenance.
- Probability reliability is required for qualification; sample size alone is insufficient.
- Out-of-policy confidence is rejected rather than clipped.
- External intelligence is routed through bounded specialist roles and cannot acquire capital authority.
- An authenticated Deriv verify-only lifecycle evidence job has been added to the existing workflow architecture.

## CI / assurance evidence

The latest commit has no status checks attached according to the connected GitHub status API. The connected GitHub workflow-run lookup for the latest commit returned no workflow runs. This is not treated as a CI pass.

The repository's engineering claims therefore remain separated from fresh execution evidence. No unsupported test, soak, broker, or deployment result is being promoted to PASS.

## Capital safety

`config/LIVE_LOCK.yaml` remains:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

No research/intelligence source has capital authority. Live orders remain zero.

## Fresh external infrastructure check

The existing Railway project `AURELIA-Production-Worker` exists with a production environment, but it currently has zero services and zero deployments.

A fresh deployment attempt against:
- project: `AURELIA-Production-Worker`
- environment: `production`
- repository: `Anto-30/aurelia-trading`
- branch: `main`
- intended service: `aurelia-production-worker`

was rejected by Railway with: `Your trial has expired. Please select a plan to continue using Railway.`

Therefore:
- no substitute worker was created;
- no deployment success is claimed;
- no production secrets were modified;
- the existing capital-protection state is unchanged.

## Remaining mandatory blockers

1. Railway production worker/plan availability.
2. Protected authenticated Deriv runtime session.
3. Broker-confirmed end-to-end transaction/fill lifecycle, performed only through the existing capital plane after its own release gate authorizes it.
4. Post-transaction ledger and reconciliation evidence.
5. Production-worker 3,600-second soak and restart/recovery evidence.
6. Prospective multi-day OOS qualification.
7. Probability calibration and drift qualification.
8. Net execution-cost/economics qualification, including the required quoted-contract sample and positive net-return criterion.
9. Fresh CI/assurance execution evidence on the current main tip.
10. Final evidence-backed release-gate decision.

Passing repository tests, research recommendations, or authenticated session checks alone do not satisfy these gates.

## Intelligence-source authority contract

All external intelligence follows:

`source -> specialist agent -> normalized evidence -> provenance/confidence -> deterministic validation -> existing release gate`

GitHub, CodeRabbit, Next Stock Outlook, The Fly Market Intelligence, Sixtyfour Intelligence, Code Tytor: Python, Notion, Outlook/Email, external repositories, plugins, and MCP sources remain non-authoritative. They cannot authorize capital, mutate `LIVE_LOCK`, read production secrets, submit broker transactions, or override deterministic validation.

## Current decision

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`LIVE_ORDERS=0`

This record is an operational status snapshot, not a live-capital authorization.


## CI hardening completed

Two explicit GitHub Actions workflows are now present on `main`:

- `.github/workflows/assurance.yml`: assurance tests, runtime tests, container health smoke test, and capital-protection assertions.
- `.github/workflows/deriv-auth-evidence.yml`: scheduled/manual authenticated Deriv verification only; it explicitly asserts zero orders and no capital authority.

The workflows do not alter `LIVE_LOCK` and do not submit orders. The connected GitHub workflow-run API currently reports no run for the latest workflow commit, so CI execution is not represented as PASS until GitHub supplies actual run evidence.
