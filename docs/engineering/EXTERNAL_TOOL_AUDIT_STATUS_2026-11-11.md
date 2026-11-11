# External Tool Audit Status — 2026-11-11

## Executive result

This batch is registered and has received targeted source-level review. It is **not fully security-certified**. No external package, action, skill bundle, agent runtime or sandbox was installed or executed. No SBOM, dependency vulnerability scan, secret scan, malware scan or dynamic isolation test was produced.

The source findings below are based on exact pinned commits recorded in `config/external_tool_intake_2026-11-11_addendum_02.json`. A commit pin establishes repeatability, not safety.

## Findings and disposition

### 1. `penvhq/penv-run` — high risk for AURELIA CI; do not adopt

Inspected: `action.yml`, `main.mjs`, `api.mjs`, `deliver.mjs`, `revoke.mjs`, `mask.mjs`, `names.mjs`, `api.test.mjs`, `deliver.test.mjs`, `revoke.test.mjs`, `package.json`.

The action exchanges a GitHub OIDC token for a penv credential, reads configured secret values, and runs the caller-supplied Bash command with those values in its child-process environment. It removes a number of runner-only variables from the child environment and writes temporary secret files under `RUNNER_TEMP` with mode 0600, removing them in a `finally` block. These are useful containment controls, but not a boundary against malicious steps in the same job.

The upstream action explicitly states that a malicious same-job step can inspect runner process memory and that end-of-job revocation is best-effort. The server-side short credential TTL is the actual time bound. Secret masking is a log hygiene measure, not a security boundary.

**Decision:** do not use this action in AURELIA workflows, especially any job that runs untrusted PR code. Do not deliver Deriv, broker, deployment or production secrets. The two supplied identical YAML entries are one duplicate and should not be repeated. The required inputs `audience` and `run` are absent from the snippet. The upstream action recommends a full 40-character commit SHA, not `@v1.0.0`.

### 2. `vercel-labs/agent-browser` — sandbox-only

Inspected: `package.json`, `scripts/postinstall.js`, `bin/agent-browser.js`, `cli/src/browser_security.rs`, `cli/src/native/browser.rs`, `cli/src/mcp.rs`, sandbox MCP and Vercel integration sources.

The CLI is a high-capability browser controller: it can connect to or launch browsers, interact with pages, execute page JavaScript, upload files and inspect network requests. Its postinstall can download a native binary from a GitHub release URL, follows redirects, and no checksum/signature verification was observed in the inspected postinstall path.

**Decision:** no install or authenticated profile access. Any future evaluation must use a disposable browser profile, synthetic credentials, restricted egress and independently verified binary provenance. Never connect it to a signed-in production browser or broker session.

### 3. `openai/codex-security` — promising security scanner; no AURELIA scan yet

Inspected: `action.yml`, `github-action/package.json`, `github-action/src/main.ts`, `github-action/src/inputs.ts`, `github-action/src/runtime.ts`, `github-action/src/artifacts.ts`, `Dockerfile`, `SECURITY.md`.

The Action captures the selected provider credential and constructs a fresh scanner environment rather than copying the entire runner environment. It supports repository/diff scope, cost/time controls, validated reports and optional GitHub artifact uploads. Its runtime uses Codex sandbox preflight; on eligible GitHub-hosted Ubuntu runners it may attempt privileged installation of bubblewrap/AppArmor when the sandbox is unavailable. Report artifacts can contain source and vulnerability details; upload is optional and disabled by default.

**Decision:** do not add to AURELIA CI or scan proprietary AURELIA source until provider processing, data retention, telemetry, permissions, report contents, artifact retention and cost policy are explicitly approved. First test only against a synthetic repository. Scanner output must not approve its own patches or releases.

### 4. `whchien/ai-trader` — research only; do not expose its MCP server

Inspected: `ai_trader/mcp/server.py`, `ai_trader/mcp/tools/backtest.py`, `ai_trader/mcp/tools/data.py`, `ai_trader/mcp/tools/strategies.py`, and the repository manifests/README.

The MCP server exposes backtest, quick-backtest, market-data fetch and strategy-list tools. The backtest request accepts a configuration-file path; quick backtest accepts a data-file path; the data-fetch tool accepts an output directory and writes CSV/SQLite data. These are local filesystem and network capabilities, not a multi-tenant sandbox. The declared GPL-3.0 licence also needs compatibility review before any code reuse. Its documented market scope is stocks, Taiwan stocks, crypto, forex and VIX—not Deriv synthetic indices.

**Decision:** research only. Do not expose this MCP server to untrusted clients or the AURELIA runtime. Before any reuse, require GPL review, path confinement, dependency/SBOM audit, data provenance, no-lookahead tests, realistic fees/slippage, and instrument-specific validation.

### 5. `shadcn/improve` — MIT, selective skill candidate

Inspected: `README.md`, `LICENSE.md`, `skills/improve/SKILL.md`, `skills/improve/references/audit-playbook.md`, `skills/improve/references/plan-template.md`. The full 16-blob repository tree was inventoried.

The licence is MIT; the earlier intake statement that no root licence was found was incorrect because the file is named `LICENSE.md`. The skill describes itself as read-only on source code, limiting its own writes to plan files. Its optional execute flow dispatches a separate executor in an isolated git worktree and states that the advisor does not merge, push or commit. The optional `--issues` mode publishes GitHub issues.

**Decision:** eligible for selective skill review, not yet installed. Confirm that the actual host enforces a disposable worktree and leave issue publishing disabled unless explicitly approved.

### 6. `addyosmani/agent-skills` — selective reference only

Inspected: MIT licence, security-and-hardening and shipping-and-launch skill guidance, session-start hook and command validator.

The repository includes skills, slash commands and optional hooks. The inspected session-start hook injects meta-skill text only when wired by a host. Shipping guidance is not release authorization.

**Decision:** no bulk import and no hooks installed. Select individual text-only skills after checking their commands, filesystem and network permissions. AURELIA release authority remains separate.

### 7–9. Reference-only decisions

- `anandanand84/technicalindicators`: old TypeScript indicator implementation. Formula reference only; no runtime dependency. Independently verify formulas and reject traded-volume assumptions where Deriv synthetic feeds do not provide real traded volume.
- `meta/astryx`: very large React/StyleX design-system repository, unrelated to AURELIA's trading runtime. No adoption.
- `TheAlgorithms/Java`: educational algorithms reference, not a validated trading strategy or backtesting library. No adoption.

## PR and CI state

- PR #299 is **closed and unmerged**. Its head is `4e3bd5d276ec7ed92df6551978413010c4868b26`; it targets PR #298's branch, not `main`. It was not reopened or merged.
- On that exact head, Ruff Static Checks run `43017999280` passed, and AURELIA Assurance run `43017999450` passed.
- PR #298 remains open, unmerged, and targets PR #292's security branch. Its Assurance run `42642406134` passed. A Vercel status failure was returned with a build-rate-limit/plan-upgrade URL; a separate Vercel deployment status was successful.
- PR #292 remains open and unmerged against `main`. Its Assurance run `42660230231`, Agent Continuity Watchdog `42660230259`, and Agent Federation Audit `42660230229` all passed. Passing CI does not replace the required independent human/security review or signed-commit requirements.

The PR dependency order remains #292 → #298 → #299. Do not merge a child PR ahead of its parent or bypass independent review, signed commits or security workflow requirements. PR #299 was left closed rather than reversing that repository state.

## What is complete versus pending

| Work item | Status |
|---|---|
| Register eight repository URLs plus deduplicated Penv action | Complete |
| Pin source commits and assign review roles | Complete |
| Repair earlier batch-1 agent assignment JSON | Complete |
| Correct `shadcn/improve` licence record to MIT | Complete |
| Targeted source review of high-risk entrypoints | Partial; findings recorded |
| Full line-by-line audit of every repository | Not complete |
| SBOM generation | Not run |
| Dependency vulnerability scan | Not run |
| Secret and malware scans | Not run |
| Dynamic sandbox, egress, filesystem escape and credential leakage tests | Not run |
| Execute upstream unit tests | Not run |
| Install packages, skills, actions or agent runtimes | Not performed |
| Modify GitHub Actions to use Penv or Codex Security | Not performed |
| Merge PR #299 or alter PR dependency order | Not performed |
| Change LIVE_LOCK, broker access, capital or execution authority | Not performed |

## Remaining hard blockers

1. No connected, attributable ClaudeCode, JEV, Dev, DeepSeek Harness, Hermes or PlaywrightCLI execution evidence was available in this session. The routing matrix is not proof that those agents ran.
2. No disposable execution environment was provisioned for upstream dynamic testing.
3. No approved provider credential or data-processing decision exists for running Codex Security on AURELIA source.
4. No independent reviewer approval was evidenced for the security parent PR.
5. The PR chain remains open/closed in a state that requires human review and sequencing; PR #299 is closed/unmerged.
6. Operational Deriv account evidence remains blocked because no genuine read-only account scope has been established. Public market-data CI is not account/broker authorization evidence.

## Safety invariant

AURELIA remains the only deterministic policy, risk, capital and execution authority. External repositories and agents receive no production secrets, Deriv credentials, broker access, order submission, capital authority, LIVE_LOCK mutation, production deployment or release authority. `LIVE_EXECUTION=BLOCKED` and `FINAL_EXECUTION_AUTHORIZATION=false` remain unchanged.
