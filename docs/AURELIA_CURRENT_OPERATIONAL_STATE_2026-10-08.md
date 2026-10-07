# AURELIA Current Operational State — 2026-10-08

## Source of truth

- Repository: `Anto-30/aurelia-trading`
- Branch: `main`
- Active deployment policy: `config/deployment_policy.json`
- Active deployment workflow: `.github/workflows/self-hosted-runtime-deploy.yml`
- Active deployment script: `scripts/deploy/bootstrap_and_deploy.sh`
- Live-release control: `config/LIVE_LOCK.yaml`

## Deployment architecture change

The Railway deployment path has been removed from the active repository surface after repeated account-level rejection caused by the expired Railway trial.

AURELIA now uses a provider-neutral self-hosted Linux/Docker deployment contract. The runtime can be placed on a user-controlled Linux host without changing the trading engine or capital controls.

The former OCI-specific deployment workflow and script were also removed in favor of the generic host implementation. OCI Always Free remains a compatible infrastructure choice, but it is not required by the software.

## What is verified

- The Railway-specific active workflow and `railway.toml` have been removed.
- The provider-specific OCI workflow and deployment script have been removed.
- A generic persistent-host deployment policy has been added.
- A generic deployment workflow now uses exact-commit SSH transport with strict known-host verification.
- The existing AURELIA Docker runtime remains the deployment unit.
- Persistent runtime state is designed to survive container restarts under `/var/lib/aurelia`.
- VERIFY_ONLY remains the default.
- Deployment infrastructure cannot mutate the checked-in LIVE_LOCK.
- The previous TDD red test for the replacement contract failed for the expected missing-file/removal conditions before implementation.

## What is not yet verified

No user-controlled host is connected to the current engineering session. Consequently:

- no persistent host handshake has been performed;
- no real self-hosted production worker has been deployed from this session;
- no production-host health check has been observed;
- no authenticated Deriv session has been independently verified here;
- no real broker transaction/fill lifecycle has been executed;
- no production 3,600-second soak has been evidenced;
- strategy qualification, calibration/drift, and net economics remain incomplete.

These are intentionally not converted into PASS states.

## Capital safety

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`live_trading_enabled=false`

`capital_plane_mode=VERIFY_ONLY`

No infrastructure change in this transition authorizes capital movement.

## Required host-side configuration

The generic deployment workflow requires protected GitHub Actions secrets:

- `AURELIA_HOST`
- `AURELIA_USER`
- `AURELIA_SSH_KEY`
- `AURELIA_KNOWN_HOSTS`

Deriv credentials must remain only in the protected runtime secret store on the host when they are eventually required. They must never be committed or printed.

## Release path after host connectivity exists

`exact main commit -> green assurance -> strict SSH transfer -> immutable host release -> Docker build -> persistent worker -> health verification -> authenticated Deriv verification -> genuine broker lifecycle evidence -> reconciliation -> production soak -> research/economics/calibration gates -> deterministic release gate -> LIVE_LOCK authorization`

The final stages remain fail-closed.
