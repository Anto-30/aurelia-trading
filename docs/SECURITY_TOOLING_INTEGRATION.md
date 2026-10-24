# Security Audit Skill and Obscura Evaluation

Status: proposed for review. This document does not enable live execution, deploy a browser service, or claim either upstream project has been installed.

## Upstream projects

- Cloudflare Security Audit Skill: https://github.com/cloudflare/security-audit-skill (MIT)
- Obscura: https://github.com/h4ckf0r0day/obscura (Apache-2.0)

Before vendoring either project, pin an immutable commit, review the complete source and transitive dependencies, verify the license and provenance, and record a SHA-256 digest. Do not install from a moving `main` branch in production automation.

## Phase A — security-audit skill (development-only)

Use the upstream skill only in an isolated development environment. Its intended multi-phase workflow covers reconnaissance, coverage-led hunting, independent candidate validation, schema-validated findings, and source-grounded reporting.

Rules for AURELIA:
1. Audit a clean, pinned checkout; never run untrusted target code with production credentials.
2. Disable external network access for target-controlled builds/tests unless an explicit, reviewed allowlist is required.
3. Use a sanitized environment, scratch-only write permissions, CPU/memory/time limits, and no live trading credentials.
4. Treat all findings as candidates until source locations, reachable conditions, impact, and independent verification are documented.
5. Findings can create review issues but cannot change risk policy, execution locks, release authorization, or production configuration.
6. A security audit passing is not proof of trading edge, operational readiness, or permission to trade.

Suggested installation for a local coding-agent workspace (run only after reviewing upstream files):
```sh
npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit
```
Do not run this in a production image or a trading runtime.

## Phase B — Obscura evaluation (separate sandbox, not production)

Obscura is a Rust headless browser/CDP automation project. Evaluate it only as an optional, isolated browser service for authorized documentation and UI tests. Do not use it to obtain private data, bypass access controls, or interact with brokerage/trading sessions.

Minimum controls:
- Run as a non-root user in a disposable container/VM with a read-only root filesystem where feasible.
- Bind the CDP port to loopback only; never publish it to `0.0.0.0` or the public internet.
- Require a strong, randomly generated CDP token; keep it in a secret manager, never in repository variables, source, logs, screenshots, or issue comments.
- Deny outbound network by default; allowlist only explicitly approved test domains. Block cloud metadata, localhost/host networks except the required local CDP channel, and internal control-plane endpoints.
- Use a fresh browser profile per test; no saved passwords, cookies, wallet sessions, broker sessions, or personal profiles.
- Apply CPU, memory, process, request, and wall-clock limits; capture logs without credentials.
- Pin image/binary versions and digests; scan dependencies and verify upstream release provenance.
- Never connect browser output to the Layer 6 risk engine as an authorization input.

Example local-only container invocation from upstream (review and pin the image first):
```sh
docker run -d --name obscura \
  -p 127.0.0.1:9222:9222 \
  -e OBSCURA_CDP_TOKEN="$(openssl rand -hex 32)" \
  h4ckf0r0day/obscura
```
This is a reference command, not evidence that a container was built or run. Use a managed secret injection mechanism instead of shell history in persistent environments. Do not deploy until the isolation and egress rules above are implemented and tested.

## GitHub Actions variables and secrets

No new variables or secrets are required by this documentation-only change.

- Non-secret feature switches and environment labels belong in Actions Variables.
- API tokens, CDP tokens, private keys, and passwords belong in Actions Secrets or the approved secret manager.
- Never create a secret named for a live Deriv token as part of this integration.
- Do not use GitHub Variables as a live-execution unlock. Live authorization remains fail-closed and controlled by the existing independent release/risk process.

## Acceptance checklist

- [ ] Review both upstream repositories and pin immutable commits.
- [ ] Confirm license and dependency provenance.
- [ ] Run static review and dependency scans in an isolated environment.
- [ ] Verify no credentials are present in the repository, workflow logs, or artifacts.
- [ ] Test browser egress denial and loopback-only CDP access.
- [ ] Test that audit/browser failures cannot modify risk state or execution authorization.
- [ ] Obtain independent human review before any runtime deployment.
- [ ] Keep `LIVE_EXECUTION=BLOCKED` and final execution authorization false until all separate trading release gates pass.

## Current status

Documentation and proposed controls only. Upstream tools have not been vendored, installed, built, run, or deployed by this change. No security audit, sandbox test, or soak result is claimed.
