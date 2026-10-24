---
name: obscura-sandbox
description: Use when evaluating Obscura for authorized browser automation or UI tests. Requires a separate sandbox; not for trading execution, brokerage sessions, or bypassing access controls.
---

# Obscura Browser Evaluation

Upstream: https://github.com/h4ckf0r0day/obscura
License reported by upstream repository metadata: Apache-2.0. Verify the license and immutable source revision before use.

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
1. Use a disposable container or VM and a non-root runtime identity.
2. Bind CDP to `127.0.0.1` only. Do not expose port 9222 publicly.
3. Use a random CDP authentication token supplied through a secret manager. Never commit it or log it.
4. Deny outbound traffic by default; explicitly allowlist only approved test hosts. Block metadata endpoints and internal network ranges.
5. Use an empty, ephemeral browser profile for each run.
6. Set CPU, memory, process, request-count, and wall-clock limits.
7. Pin the source commit or image digest, inspect dependencies, and verify release provenance.
8. Capture sanitized logs and remove any accidentally collected sensitive data according to the incident process.
9. Prove the sandbox cannot access trading credentials or alter execution/risk state before approving any use.

## Evaluation record
Record source commit/image digest, host and container versions, exact command, network policy, resource limits, target domains, exit status, and test artifacts. A command example is not evidence of successful execution. Stop and report blocked if any isolation guarantee is unknown.

## Upstream reference
The upstream README describes Docker use with a loopback-bound CDP port and `OBSCURA_CDP_TOKEN`. Review current upstream documentation before running; do not use a floating production image tag.
