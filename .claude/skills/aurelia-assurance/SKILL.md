---
name: aurelia-assurance
description: Evidence-led review of AURELIA blockers, tests, runtime evidence, and release gates without bypassing trading safeguards.
---

# AURELIA assurance workflow

1. Read repository instructions and current architecture before changing anything.
2. Identify the exact failure, failed test, deployment blocker, or unverified release gate. Avoid broad rewrites.
3. Parallelize independent read-only reviews using risk-reviewer, strategy-researcher, and test-validator where relevant.
4. Trace findings to source code, configuration, logs, test output, or broker/runtime evidence. Mark unsupported assumptions NOT VERIFIED.
5. Implement minimal fixes on a non-production branch. Never weaken capital authority, disable safeguards, expose secrets, or silently change risk thresholds.
6. Add regression tests including rejection and failure paths. Run relevant checks when execution tools are available and record actual outcomes.
7. Review the diff for security, architecture drift, secret leakage, and weakened safety gates.
8. Report a gate matrix with PASS/FAIL/NOT VERIFIED, changed files, test evidence, deployment evidence, residual risks, and next action.

## Release boundary

Green CI does not prove live-trading readiness. Release requires current authenticated Deriv session/account evidence, broker-verified lifecycle and transaction reconciliation, valid strategy/economic evidence, required runtime and soak assurance, and approval by the existing release authority. Stale, missing, contradictory, or unknown evidence blocks release. Agents cannot authorize capital.
