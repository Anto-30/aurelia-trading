# Skyvern Integration Intake — AURELIA

**Status:** PROPOSED / VERIFY_ONLY  
**Decision:** Accept for a bounded, read-only browser-worker proof of concept only. Do not deploy or grant trading authority based on this document.  
**Reviewed:** 2026-10-26  
**Upstream:** https://github.com/Skyvern-AI/skyvern  
**Upstream MCP guide:** https://github.com/Skyvern-AI/skyvern/tree/main/integrations/mcp  
**Upstream n8n integration:** https://github.com/Skyvern-AI/skyvern/tree/main/integrations/n8n

## Executive decision

Skyvern is an AI-assisted browser automation platform built around Playwright-compatible browser actions and workflow orchestration. Its upstream README documents an MCP server and n8n integration. This makes it a plausible auxiliary worker for evidence collection and approved administrative browser tasks. It is not a trading engine, risk authority, broker adapter, or release authority.

**No implementation, deployment, test run, or runtime connection is claimed by this intake.** This change records the proposed boundary and acceptance gates only.

## Verified upstream observations

- The repository is public, active, and uses `main` as its default branch at the time of review.
- Upstream declares AGPL-3.0. Legal review is required before distributing a modified/combined service or otherwise relying on an interpretation of the licence.
- The root `docker-compose.yml` currently publishes ports `8000` and `6080`; it mounts browser sessions and a local credential vault; it uses a `latest` image tag; and its bundled Postgres service has example credentials. These are development defaults, not an acceptable production security baseline.
- The root `.env.example` says URL validation is off by default. The example recommends enabling `ENABLE_URL_VALIDATION=true` when untrusted users can run workflows. For any isolated worker, enable URL validation and separately enforce network egress controls.
- Upstream MCP documentation describes local and cloud modes. The remote MCP endpoint is stateless; browser workflows require creating a browser session and passing its identifier on subsequent calls.
- The upstream security policy's supported-version table is generic and should not be treated as evidence of a current security-support commitment.
- A separate automated trust-score check could not be completed because its anonymous daily quota was exhausted. No external trust score or independent security certification is asserted.

Sources:
- https://github.com/Skyvern-AI/skyvern
- https://github.com/Skyvern-AI/skyvern/blob/main/docker-compose.yml
- https://github.com/Skyvern-AI/skyvern/blob/main/.env.example
- https://github.com/Skyvern-AI/skyvern/blob/main/SECURITY.md
- https://github.com/Skyvern-AI/skyvern/tree/main/integrations/mcp

## AURELIA integration boundary

### Permitted for the initial proof of concept

- Public documentation and public status-page research.
- Read-only inspection of approved, non-sensitive dashboards.
- Downloading approved public reports or CI artifacts.
- Capturing page title, URL, timestamp, task identifier, and artifact checksum as evidence.
- Producing a proposed operational report for a human or deterministic verifier to review.

### Denied

- Opening or submitting broker order forms, placing/modifying/cancelling orders, deposits, withdrawals, or any capital-moving action.
- Changing `config/LIVE_LOCK.yaml`, deployment policy, risk limits, account binding, or release authorization.
- Reading, exporting, typing, or logging broker tokens, OTPs, API keys, session cookies, credential vault contents, or other secrets.
- Treating LLM/browser output as verified broker state, risk input, or proof that a gate passed.
- Running arbitrary code blocks, arbitrary HTTP request blocks, shell commands, or unreviewed workflows in the initial proof of concept.
- Accessing loopback, RFC1918/private networks, cloud metadata endpoints, or internal control planes from the browser worker unless an explicit separately reviewed allowlist requires it.

Skyvern output is untrusted observation. It may create an evidence candidate only; a deterministic verifier must independently validate evidence before it can affect operational state. No Skyvern component receives capital-plane credentials or a direct path to execution APIs.

## Deployment security requirements

1. Use a dedicated isolated host/container and a pinned image digest or reviewed release version; do not deploy `latest` as a production pin.
2. Bind service ports to loopback or a private authenticated network. Do not expose browser streaming/VNC ports publicly.
3. Replace all example/default database credentials; keep credentials in a secret manager or runtime secret injection, never source control, workflow prompts, logs, or artifacts.
4. Enable URL validation and enforce network-level egress allowlists/deny rules to mitigate SSRF and internal-network access.
5. Disable or tightly constrain custom code, arbitrary HTTP blocks, file uploads, credential storage, and downloads until individually threat-modelled.
6. Use dedicated low-privilege identities, separate browser profiles, short-lived credentials, session expiry, and no access to personal browser profiles.
7. Sanitize page content as untrusted input; browser pages can contain prompt-injection instructions. Do not let page text change the task's authorization scope.
8. Keep audit logs for task ID, requester, approval ID, allowed domains, start/end timestamps, result status, and artifact hashes. Redact secrets and personal data.
9. Review AGPL-3.0 obligations and all transitive dependencies before distribution or production adoption.
10. Preserve AURELIA's fail-closed behaviour: missing, stale, conflicting, malformed, or unverifiable evidence means UNKNOWN and ABORT/VERIFY_ONLY.

## Proposed interface

The only initial interface should be an explicit task envelope submitted by an approved orchestrator:

- `task_id`: unique idempotency key.
- `requested_by`: authenticated service identity.
- `approval_ref`: human/policy approval record for the specific task.
- `allowed_domains`: exact host allowlist.
- `task_class`: fixed enum such as `PUBLIC_RESEARCH` or `READ_ONLY_STATUS`.
- `deadline`: bounded execution deadline.
- `artifact_policy`: permitted file types, maximum size, retention and checksum requirements.

Return only a structured result containing task ID, final status, observed URL/domain, timestamps, artifact references and SHA-256 hashes, and a concise error code. Reject free-form requests outside the allowlisted task class. Do not include credentials in task payloads.

## Acceptance gates — all required

- [ ] Repository and license review completed by a human.
- [ ] Version/digest pinned; dependency and container scan results retained.
- [ ] Network isolation verified; public access to ports 8000/6080 denied.
- [ ] URL validation and egress restrictions tested against loopback, private IP ranges, IPv6 local ranges, and cloud metadata endpoints.
- [ ] Authentication, authorization, session expiry, and audit logging verified.
- [ ] Prompt-injection test proves page instructions cannot expand allowed domains or change task permissions.
- [ ] Tests prove order-entry, capital movement, secret retrieval, config mutation, arbitrary code, and arbitrary HTTP actions are denied.
- [ ] Artifact provenance and hashes independently verified.
- [ ] Failure injection proves timeout, network error, malformed output, missing artifact, or verifier disagreement returns UNKNOWN and aborts.
- [ ] AURELIA assurance and runtime suites pass on the exact candidate commit.
- [ ] Human reviewer approves the PR before merge.
- [ ] Separate security and operational approval before any non-read-only use.

## Verification record

| Item | Result |
|---|---|
| Public repository metadata fetched | PASS |
| Upstream README and relevant configuration files inspected | PASS |
| MCP integration documentation inspected | PASS |
| Independent trust-score check | NOT RUN — provider daily quota exhausted |
| Skyvern installation or container scan | NOT RUN |
| Skyvern tests | NOT RUN |
| AURELIA integration tests | NOT RUN |
| Live runtime connection | NOT RUN |
| Trading authorization | BLOCKED / NOT GRANTED |

## Rollback

The proof of concept must be removable by disabling the dedicated worker and its credentials without changing AURELIA's capital plane, risk engine, execution firewall, broker adapter, or live-lock configuration. No release gate may depend on Skyvern being available.

## Final disposition

**Proceed only to a reviewable, read-only proof of concept after the security and acceptance gates are implemented. Do not merge this document as evidence of runtime readiness, and do not enable live trading.**