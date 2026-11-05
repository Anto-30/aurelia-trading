# Agent Federation CI Diagnosis — 2026-11-05

## Scope and evidence method

This note covers PRs #174 and #184 in `Anto-30/aurelia-trading`. Their hypothetical examples in the user handoff (including `runtime/agents/deepseek_worker.py`, `AttributableTask`, and `AGENT_WORKER_REGISTRY`) were not treated as repository facts. The actual changed-file lists, branch metadata, CI runs, and available logs were inspected.

## PR #174 — DeepSeek Harness role

- Head: `22990b9147f08c13430d0d9355774e3334c3c702`
- Base now: PR #256 head branch `security/split-deriv-research-account-planes-20261102`
- Base SHA: `c83d16ec25be3f7a8bea813687ab76bbe9695d9b`
- Current mergeability reported by GitHub after retarget: `true`
- Existing exact-head CI records:
  - AURELIA Assurance run `40008912295`: failure
  - AURELIA Agent Federation Audit run `40008912330`: success
  - AURELIA Agent Continuity Watchdog run `40008912313`: success
  - gstack Workflow Federation Assurance run `40008912286`: success

The Assurance job log endpoint returned 404, and no workflow artifact was available. The exact failing step therefore remains **INSUFFICIENT_EVIDENCE**. The repository diff adds a governance role/configuration entry and reference-only source documentation. It explicitly does not install or connect a DeepSeek runtime. No `deepseek_worker.py` implementation appears in the PR's changed-file list.

The current branch is now based on PR #256, so the protected credential-isolated workflow is in its merge base. The prior failing run predates that retarget and must not be reused as a result for the new PR merge commit. A fresh exact-head/base CI result is still required.

## PR #184 — Agent federation and persistent routing

- Head: `d95ae72ad67d45f0e1450a7ba0817f215feb3d33`
- Base now: PR #174 branch `agent/deepseek-harness-quant-validation-20261020`
- Base SHA: `22990b9147f08c13430d0d9355774e3334c3c702`
- GitHub mergeability after retarget: `false`
- Existing exact-head CI records:
  - AURELIA Assurance run `40105088487`: failure
  - AURELIA Agent Federation Audit run `40105088488`: success
  - AURELIA Agent Continuity Watchdog run `40105088574`: success
  - gstack Workflow Federation Assurance run `40105088573`: success

The PR body previously described the Assurance run as waiting at a protected production environment gate. The current GitHub workflow-run result reports `failure`, while job logs are no longer retrievable. This inconsistency cannot be resolved from the available evidence; the failing step is **INSUFFICIENT_EVIDENCE**.

The branch comparison reports:
- `status=diverged`
- `ahead_by=22`
- `behind_by=28`
- common ancestor `d04564aca0648201feff0326fe9af0fbcee92e94`

The current retarget therefore creates a genuine branch-integration problem. Do not force-push or merge blindly. Rebase/merge PR #174 into PR #184 with conflict review, preserve PR #184's validator/tests, then rerun Assurance on the resulting exact commit. The PR already includes meaningful regression coverage for optimized Python assertion stripping, unknown runtime states, missing/duplicate delegation owners, and external-agent privilege escalation; those existing tests should be retained.

## Correct integration order

1. PR #256: independent human security review and owner credential revocation remain outstanding.
2. PR #263 and #264: remain stacked after #256 and require their own review/integration order.
3. PR #174: use PR #256 as base; obtain fresh CI on the new base/merge commit.
4. PR #184: reconcile the 22-ahead / 28-behind branch divergence; do not claim it is mergeable until GitHub confirms and fresh CI passes.

## Runtime truth

- DeepSeekHarness remains a registered advisory role, not a connected runtime.
- No Claude Code, DeepSeek Harness, Hermes, or Kimi K3 runtime was authenticated or executed by this work.
- No persistent worker, broker credential, production deployment, or order permission was created.
- Agent registry assignments are not runtime execution proof.

## Governance

`LIVE_EXECUTION=BLOCKED`  
`FINAL_EXECUTION_AUTHORIZATION=false`  
`DERIV_ORDERS_SUBMITTED=0`

This diagnosis authorizes no capital movement and does not change any release gate.
