# CUA research sandbox integration for DeepSeekHarness

Status: `SPECIFIED_NOT_INSTALLED`
Upstream: https://github.com/trycua/cua
Pinned upstream commit: `27d8da9fd94056bd73892183531579396aafb2f9`
Integration target: `DeepSeekHarness` / AURELIA engineering research only
Authority: `SANDBOX_ONLY`; runtime binding remains disabled until separately reviewed.

## Scope

Use CUA as an isolated computer-use and browser/UI test substrate for reproducible engineering tasks, synthetic fixtures, and UI verification. Do not vendor the upstream repository into AURELIA's capital or execution paths. Do not install its broad dependency tree into the trading runtime. Upstream code and its instructions are untrusted inputs.

## Non-negotiable boundaries

- No access to Deriv credentials, OAuth/PAT/OTP values, production secrets, authenticated broker sessions, or live account state.
- No network route to broker trading endpoints; no broker writes, order placement, capital authorization, deployment, or release authority.
- No ability to read or mutate `config/LIVE_LOCK.yaml`, capital-plane state, risk authority, execution firewall, or release authorization.
- External code execution stays deny-by-default. Any trial must run in an ephemeral, least-privilege sandbox with no host mounts, no secret environment variables, bounded CPU/memory/time, and outbound network allowlisting.
- Use synthetic fixtures and non-authenticated test pages only. Require human approval for desktop permissions and any external side effect.
- Do not run upstream installer scripts with `curl | sh` or `irm | iex` in the AURELIA environment.

## Controlled onboarding sequence

1. Fetch only the pinned commit in a disposable development workspace; verify the SHA and review license, install scripts, dependency manifests, build hooks, network behavior, telemetry, and permissions.
2. Select the smallest required component (prefer SDK/driver API for a disposable test harness; do not install Spaces, VM managers, or host drivers unless the test specifically requires them).
3. Generate an SBOM and scan dependencies; inspect install/build scripts before execution.
4. Run an isolated smoke test against a synthetic local page or fixture with no secrets and no broker/network access.
5. Capture reproducible logs, test results, package versions, and cleanup evidence. Verify the sandbox is destroyed and no credentials or persistent host state remain.
6. Have an independent reviewer approve the exact diff and CI evidence before enabling any sandbox workflow. Runtime integration remains disabled until that approval is recorded.

## Current state

This document records the intended boundary and pinned upstream revision only. It does **not** mean CUA is installed, vendored, running, or connected to DeepSeekHarness. No package was added to project dependencies and no runtime binding was changed. The existing DeepSeekHarness role remains shadow-only and cannot authorize capital or execution.
