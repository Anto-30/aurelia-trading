---
name: security-audit-integration
description: Use when conducting a source-grounded security audit of AURELIA, validating security findings, or planning use of Cloudflare's security-audit skill. Development-only; never authorizes live trading.
---

# AURELIA Security Audit Integration

## Scope
Use Cloudflare's upstream skill as a reviewed development-time methodology, not a runtime dependency. Upstream: https://github.com/cloudflare/security-audit-skill

Review pin observed 2026-10-24: `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`. GitHub reports this commit as unsigned/unverified; this is not cryptographic provenance. Resolve that caveat through an independent trusted channel before installing. Re-check the current upstream reference and record a source archive digest.

## Required workflow
1. Identify the exact repository commit, language/runtime, trust boundaries, external inputs, secrets boundaries, and execution/risk authorization boundaries.
2. Review current source and dependency lockfiles before proposing changes. Never assume a path, API response, test result, or vulnerability.
3. Run target-controlled code only in an OS-enforced sandbox with outbound networking disabled by default, sanitized environment variables, resource limits, and scratch-only write permissions.
4. Separate findings into confirmed, needs-validation, and rejected. A confirmed finding must include exact source evidence, reachable preconditions, demonstrated impact, and independent verification. If a fact is missing, report needs-validation rather than guessing.
5. Record the commit hash, source digest, tool versions, commands, exit codes, timestamps, and artifacts. Do not claim tests or audits ran unless they actually ran.
6. Recommend the smallest patch. Never edit risk thresholds, execution locks, credentials, or release authorization as a side effect of an audit.
7. Request independent human review before merging security-sensitive changes.

## AURELIA-specific checks
- Layer 6 rejects on exceptions, timeout, invalid/stale state, missing inputs, or unknown state.
- Strategy code and LLM agents cannot directly authorize capital or bypass deterministic risk checks.
- Fail-closed execution locks and release gates remain authoritative.
- Secrets are not logged, committed, included in screenshots, or copied into findings.
- Browser automation, if used, is isolated and cannot access trading sessions or execution credentials.

## Installation gate
Do not automatically install from a moving branch or run an unpinned installer. First resolve the upstream provenance caveat, inspect the installation mechanism and dependencies, then install only the exact reviewed commit in a disposable local development workspace. Never install in a production runtime or a workflow with production secrets.

## Output
Produce a concise report with scope, commit, source digest, methods, verified findings, unresolved questions, false positives rejected, test evidence, limitations, and recommended remediations. Security review is not evidence of profitable trading or live-readiness.
