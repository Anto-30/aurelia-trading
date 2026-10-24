# Security Audit Skill and Obscura Evaluation

Status: proposed for review. This document does not enable live execution, deploy a browser service, or claim either upstream project has been installed.

## Upstream projects and review pins

- Cloudflare Security Audit Skill: https://github.com/cloudflare/security-audit-skill
  - License: MIT (upstream LICENSE inspected)
  - Review pin: `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`
  - Provenance caveat: GitHub reports this commit's signature as unverified/unsigned. Treat the pin as a source locator, not as cryptographic provenance proof. Verify through an independent trusted channel before installation.
- Obscura: https://github.com/h4ckf0r0day/obscura
  - License: Apache-2.0 (upstream repository metadata)
  - Review pin: `09790944a405ba81a7df27bc2577c6b0db283900`
  - Provenance caveat: GitHub reports this commit's signature as verified. Still inspect the full source, dependencies, release artifacts, and build provenance before execution.

These are review pins observed on 2026-10-24, not blanket approval to install. Re-check the upstream refs before use. Record source archive SHA-256, dependency lockfiles, toolchain versions, and artifact digests for any approved build. Do not install from a moving `main` branch in production automation.

## Phase A — security-audit skill (development-only)

Use the upstream skill only in an isolated development environment. Its intended workflow supports multi-phase auditing, independent candidate validation, structured findings, and source-grounded reporting.

Rules for AURELIA:
1. Audit a clean, pinned checkout; never run untrusted target code with production credentials.
2. Disable external network access for target-controlled builds/tests unless an explicit, reviewed allowlist is required.
3. Use a sanitized environment, scratch-only write permissions, CPU/memory/time limits, and no live trading credentials.
4. Treat all findings as candidates until source locations, reachable conditions, impact, and independent verification are documented.
5. Findings can create review issues but cannot change risk policy, execution locks, release authorization, or production configuration.
6. A security audit passing is not proof of trading edge, operational readiness, or permission to trade.

Do not install automatically through an unpinned command. After the upstream source, install mechanism, and dependencies are reviewed, install the exact reviewed commit in a disposable local coding-agent workspace. Do not install in a production image or a workflow with production secrets.

## Phase B — Obscura evaluation (separate sandbox, not production)

Obscura is a Rust headless browser/CDP automation project. Evaluate it only as an optional, isolated browser service for authorized documentation and UI tests. Do not use it to obtain private data, bypass access controls, or interact with brokerage/trading sessions.

Minimum controls:
- Build from the reviewed commit in a disposable, isolated build environment. Do not assume an unverified container image exists or is official; no image reference is approved by this document.
- Run as a non-root user in a disposable container/VM with a read-only root filesystem where feasible.
- Bind host-published CDP access to `127.0.0.1` only. Obscura may bind to `0.0.0.0` inside the container for port forwarding; never publish the host port to public interfaces.
- Require a strong, randomly generated CDP token whenever the server binds to a non-loopback interface. Supply it through a secret manager, never commit or log it.
- Deny outbound traffic by default; allowlist only approved test hosts. Block metadata endpoints and internal network ranges, except explicitly necessary local control channels.
- Use a fresh, ephemeral browser profile per test; no saved passwords, cookies, wallet sessions, broker sessions, or personal profiles.
- Apply CPU, memory, process, request, and wall-clock limits; capture sanitized logs.
- Pin source, dependencies, toolchain, and resulting artifact digests; scan dependencies and verify build provenance.
- Never connect browser output to the Layer 6 risk engine as an authorization input.

Do not run a container command until the exact image or build artifact has been independently verified and the network policy has been implemented and tested. Example commands in upstream documentation are not evidence that AURELIA has built or tested the service.

## GitHub Actions variables and secrets

No new variables or secrets are required by this documentation-only change.

- Non-secret feature switches and environment labels belong in Actions Variables.
- API tokens, CDP tokens, private keys, and passwords belong in Actions Secrets or the approved secret manager.
- Never create a secret for a live Deriv token as part of this integration.
- Do not use GitHub Variables as a live-execution unlock. Live authorization remains fail-closed and controlled by the existing independent release/risk process.

## Acceptance checklist

- [ ] Independently verify upstream provenance; resolve the unsigned Cloudflare commit provenance caveat.
- [ ] Review full upstream source and dependency lockfiles at the pinned commits.
- [ ] Confirm licenses, transitive dependency licenses, and build provenance.
- [ ] Run static review and dependency scans in an isolated environment.
- [ ] Verify no credentials are present in repository content, workflow logs, or artifacts.
- [ ] Build Obscura only in a disposable environment and verify its runtime configuration.
- [ ] Test browser egress denial, metadata blocking, and host-loopback-only CDP access.
- [ ] Test that audit/browser failures cannot modify risk state or execution authorization.
- [ ] Obtain independent human review before any runtime deployment.
- [ ] Keep `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and capital plane in `VERIFY_ONLY` until all separate trading release gates pass.

## Current status

Documentation and proposed controls only. Upstream tools have not been vendored, installed, built, run, or deployed by this change. No security audit, sandbox test, or soak result is claimed. GitHub Actions Assurance is waiting; do not treat a waiting run as a pass or bypass any required approval.
