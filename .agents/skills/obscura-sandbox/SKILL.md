---
name: obscura-sandbox
description: Use when evaluating Obscura for authorized browser automation or UI tests. Requires a separate sandbox; not for trading execution, brokerage sessions, or bypassing access controls.
---

# Obscura Browser Evaluation

Upstream: https://github.com/h4ckf0r0day/obscura
License: Apache-2.0 (upstream repository metadata).
Review pin observed 2026-10-24: `09790944a405ba81a7df27bc2577c6b0db283900`. GitHub reports this commit signature as verified. This is a source review pin, not approval to deploy. Re-check the upstream ref, inspect full source and dependencies, and record source/archive and resulting artifact digests.

## Permitted scope
- Public documentation research where automated access is permitted.
- Local UI smoke tests against a dedicated non-production test environment.
- Screenshot and page-rendering checks using synthetic test data.

## Prohibited scope
- Accessing or automating live Deriv/brokerage sessions, wallets, or trading accounts.
- Storing or reusing personal cookies, passwords, session tokens, or profiles.
- Connecting browser results directly to Layer 6, strategy signals, order placement, or live authorization.
- Circumventing authentication, authorization, CAPTCHAs, rate limits, or site restrictions.
- Unrestricted browsing from a machine holding production credentials.

## Required isolation controls
1. Build and run only in a disposable container or VM; use a non-root runtime identity.
2. Publish CDP to host loopback only. The upstream Dockerfile's server binds to `0.0.0.0` inside the container for port forwarding; this does not justify exposing the host port publicly.
3. Supply a strong random CDP token through a secret manager whenever the server binds to a non-loopback interface. Never commit or log it.
4. Deny outbound traffic by default; explicitly allowlist only approved test hosts. Block metadata endpoints and internal network ranges.
5. Use an empty, ephemeral browser profile for each run.
6. Set CPU, memory, process, request-count, and wall-clock limits.
7. Pin source, dependency lockfiles, toolchain, and output artifact digests. Inspect release provenance; do not assume an unverified image is official.
8. Capture sanitized logs and remove any accidentally collected sensitive data according to the incident process.
9. Prove the sandbox cannot access trading credentials or alter execution/risk state before approving any use.

## Evaluation record
Record source commit/archive digest, build tool versions, artifact digest, exact command, network policy, resource limits, target domains, exit status, and test artifacts. A command example is not evidence of successful execution. Stop and report blocked if any isolation guarantee is unknown.

## Upstream reference
Review the upstream README and Dockerfile at the pinned commit before building. Do not pull a floating image or deploy until the artifact and runtime configuration are independently verified. Obscura's anti-detection capabilities are not to be used to evade access controls or site restrictions.
