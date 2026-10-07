# AURELIA Provider-Neutral Persistent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the expired Railway dependency from AURELIA's active deployment path and replace it with a provider-neutral self-hosted Linux runtime that uses immutable source releases, automatic restart, strict health verification, and the existing AURELIA capital controls.

**Architecture:** AURELIA will deploy to a user-controlled Linux host over strict SSH. GitHub Actions transports the exact `main` commit as an immutable archive; the host builds the existing Docker runtime, persists runtime state outside the container, and restarts it automatically. Deployment mode is derived from `config/LIVE_LOCK.yaml`; deployment infrastructure cannot mutate the lock or grant capital authority.

**Tech Stack:** GitHub Actions, Python 3.13, Docker, POSIX shell, systemd-independent Docker restart policy, JSON deployment policy, existing AURELIA health endpoint and LIVE_LOCK.

**Spec:** User request in the current task plus existing AURELIA capital-plane/release-gate contracts.

## Global Constraints

- The existing AURELIA runtime, capital plane, Risk Warden, Execution Firewall, Deriv adapter, ledger, fencing, reconciliation, watchdog, and LIVE_LOCK remain authoritative.
- `FINAL_EXECUTION_AUTHORIZATION` must not be created or flipped by deployment infrastructure.
- `LIVE_EXECUTION` remains blocked unless the checked-in LIVE_LOCK already authorizes LIVE and all release gates pass.
- Secrets must remain outside Git history, source archives, artifacts, and logs.
- Railway must not be a required dependency of CI, deployment, runtime, or release documentation.
- The replacement must not depend on an expiring promotional platform entitlement.
- The deployment target must remain interchangeable: a user-controlled Linux VM/server is the compute authority; OCI Always Free is an optional compatible host, not a runtime dependency.
- Deployment verification must prove exact source SHA, running container identity, health, persistence, and fail-closed capital state.

## Review Focus

- Accidental live-capital enablement during deployment: test that VERIFY_ONLY stays blocked and LIVE still requires the checked-in lock.
- Reintroduced Railway coupling: test active workflows/config contain no Railway deployment dependency.
- Secret leakage: test deployment files never embed broker credentials or print secret values.
- Runtime drift: test the host records the exact source SHA and health state.
- Host-loss/restart behavior: test Docker restart policy and persistent `/var/lib/aurelia` state are configured.

### Task 1: Deployment Contract Red Test

**Files:**
- Create: `tests/test_self_hosted_deploy_contract.py`

**Interfaces:**
- The test defines the required paths and deployment-policy fields for Tasks 2–4.

- [ ] **Step 1: Write the failing test** asserting:
  - `config/deployment_policy.json` exists and declares `primary_provider=self_hosted`, `no_trial_dependency=true`, and `capital_authority=LIVE_LOCK_only`.
  - `.github/workflows/self-hosted-runtime-deploy.yml` exists.
  - `scripts/deploy/bootstrap_and_deploy.sh` exists.
  - the old Railway workflow and `railway.toml` do not exist.
  - the deployment script contains `--restart unless-stopped` and health verification.

- [ ] **Step 2: Run the test and verify it fails because the replacement contract does not yet exist.**

- [ ] **Step 3: Commit the red test.**

### Task 2: Provider-Neutral Host Runtime

**Files:**
- Create: `config/deployment_policy.json`
- Create: `scripts/deploy/bootstrap_and_deploy.sh`
- Delete: `scripts/oci/bootstrap_and_deploy.sh`

**Interfaces:**
- Input: source commit SHA and `AURELIA_DEPLOYMENT_MODE`.
- Output: running Docker container `aurelia-runtime`, durable deployment lineage under `/var/lib/aurelia`, and health evidence.
- The script must reject invalid deployment modes and enforce the checked-in LIVE_LOCK state before starting the container.

- [ ] **Step 1: Implement the minimal generic host bootstrap/deploy behavior required by the red test.**
- [ ] **Step 2: Run the contract test and the shell syntax check; both must pass.**
- [ ] **Step 3: Commit the runtime implementation.**

### Task 3: Replace Railway CI With Self-Hosted Deployment Transport

**Files:**
- Create: `.github/workflows/self-hosted-runtime-deploy.yml`
- Delete: `.github/workflows/railway-deploy.yml`
- Delete: `.github/workflows/oci-free-host-deploy.yml`

**Interfaces:**
- Inputs: `AURELIA_HOST`, `AURELIA_USER`, `AURELIA_SSH_KEY`, `AURELIA_KNOWN_HOSTS` stored as protected GitHub Actions secrets.
- The workflow must require green AURELIA Assurance for the exact commit.
- The workflow transfers only the exact commit archive and never prints secret values.
- The workflow must verify exact source SHA, runtime mode, container health, and capital-protection state after deployment.

- [ ] **Step 1: Implement the new workflow with VERIFY_ONLY as the default.
- [ ] **Step 2: Remove the obsolete Railway and OCI-specific deployment workflows.
- [ ] **Step 3: Run YAML/static contract checks and the repository assurance tests.
- [ ] **Step 4: Commit the workflow replacement.**

### Task 4: Remove Expired Railway Surface and Refresh Operational Documentation

**Files:**
- Delete: `railway.toml`
- Delete: `tests/test_railway_deploy_contract.py`
- Create: `docs/AURELIA_SELF_HOSTED_RUNTIME_2026-10-08.md`
- Create: `docs/AURELIA_CURRENT_OPERATIONAL_STATE_2026-10-08.md`
- Modify: `README.md`
- Modify: `AURELIA_SOURCE_OF_TRUTH.json`
- Modify: `AURELIA_REPOSITORY_MAP.md`

**Interfaces:**
- Documentation must identify self-hosted Linux as the deployment authority and OCI Always Free only as one compatible host option.
- Documentation must clearly distinguish infrastructure readiness from live trading authorization.
- Historical Railway status snapshots remain immutable; current documentation must not treat them as active deployment requirements.

- [ ] **Step 1: Write the replacement documentation and source-of-truth fields.
- [ ] **Step 2: Delete obsolete Railway deployment config/test files.
- [ ] **Step 3: Run documentation/config validation and full test suites.
- [ ] **Step 4: Commit the cleanup.**

### Task 5: Fresh CI Verification and Review

**Files:**
- No new production files.

- [ ] **Step 1: Verify the latest main commit and changed-file set.
- [ ] **Step 2: Inspect the new workflow run and assurance run for the exact commit.
- [ ] **Step 3: Verify the Railway workflow is absent and no Railway deployment path is active.
- [ ] **Step 4: Request code review on the completed diff.
- [ ] **Step 5: Only report completion for the repository change after fresh CI evidence is green.

## Explicit Non-Goals

- Do not delete or bypass `config/LIVE_LOCK.yaml`.
- Do not enable LIVE execution.
- Do not fabricate authenticated Deriv evidence or broker fills.
- Do not treat a self-hosted deployment as proof that the strategy is qualified.
- Do not promise that any third-party cloud provider can never change policy; the design specifically removes reliance on an expiring trial entitlement.
