# AURELIA Repository Federation and Agent Tooling Plan — 2026-10-12

## Purpose and truth-in-status
This document is the canonical intake and assignment manifest for repository candidates supplied across the 2026-10-12 intake work. It is a plan and triage record, not proof that repositories were cloned, installed, synchronized to agent runtimes, or executed. The connected GitHub integration can update this repository's documentation and inspect remote files; it does not expose a shell or a connected desktop workspace for bulk cloning. Do not claim physical synchronization until an actual workspace inventory and commit-pinned checkout evidence exist.

Canonical system: `Anto-30/aurelia-trading`, `main`. Review branch: `research/repository-intake-2026-10-12`.

## Non-negotiable architecture and permissions
- One canonical AURELIA engine, one capital plane, one release authority, one evidence lineage.
- All external repositories and agent-generated code are untrusted inputs. Never merge external runtime code directly into `main`.
- Research agents may read market data, papers, source code and sanitized logs; they may not hold broker credentials or submit orders.
- Only the deterministic AURELIA Risk Warden, Execution Firewall, broker-truth checks, idempotency/transaction-verification path and existing release gate can control capital eligibility. LLM consensus is advisory only.
- Keep live execution locked and verify-only until all required authenticated broker, recovery, soak, prospective OOS, calibration, economics, security, deployment and strategy-eligibility evidence is produced and reviewed.
- Never put tokens, API keys, passwords, account identifiers, pairing codes or production configuration into source, issue comments, agent prompts or chat.
- Every candidate adoption requires pinned commit, verified license, dependency/security scan, source review, reproducible tests, explicit interface, owner, rollback and review.

## Newly supplied repositories — README/license screening
These are remote README/license spot-checks only; no code was cloned or executed.

| Repository | What README suggests | License / risk signal | Disposition |
|---|---|---|---|
| `ajvizganapathy-pixel/emmanuel-trades-mastery` | Single-file HTML/CSS/JS trading education dashboard, illustrative strategy cards, charts and risk calculator; README includes placeholder demo links and a roadmap that lists live data/backtesting as future work. | MIT LICENSE present. README marketing metrics and “production ready” status are unverified. | P2 education/UI reference. Do not treat displayed signals, stats or calculators as validated strategy logic. Check HTML/JS for remote calls and dependency/CDN use before reuse. |
| `Rime504/Trading_Algo` | Semi-automated Confirmation Model workflow; README describes Interactive Brokers/TWS historical data, liquidity sweep/HTF FVG/iFVG/CISD confirmations, position sizing, Discord/Telegram alerts and CSV backtesting. README includes a `main.py` labelled live trading but elsewhere describes manual execution/read-only use. | No top-level LICENSE file was found; README says personal use only and prohibits redistribution/sale without permission. Conflicting execution descriptions. | Hold/reject for code reuse until owner grants explicit written permission and the actual order path is reviewed. Extract methodology as a hypothesis only, then independently implement and test. Never run `main.py`. |
| `Ianomosh/forex-multi-agent` | README states an experimental Python Forex analysis system where strategy agents reach consensus before producing a signal; explicitly says early development. | No top-level LICENSE file found; very limited README evidence. | Reference-only; no copying or execution until license, code, dependencies and agent boundaries are reviewed. Any consensus remains advisory, never capital authority. |
| `p1cxi/silent-hill-conky-configuration` | Linux Conky desktop widget for Trading212 portfolio/account data, headlines, weather and system monitoring; includes setup script and a Trading212 API integration. | MIT LICENSE present. README's credential example describes API keys/secrets with account access; shell setup and network/API calls require review. Desktop/Linux-specific; not a mobile agent sync solution. | P2 optional monitoring/UI reference only. Do not import Trading212 credentials or connect it to AURELIA's Deriv capital plane. Inspect scripts and credential storage before any sandbox use. |

## Consolidated repository queue
The prior intake entries in `docs/REPOSITORY_INTAKE_2026-10-12.md` and `docs/REPOSITORY_TRIAGE_DESKTOP_FOLLOWUP_2026-10-12.md` remain in scope. This includes the initial P0 quantitative/broker candidates (Jesse, Hummingbot, OctoBot, CCXT, FinRL-related projects, derivative/Deriv bot candidates and research libraries), P1 agent/developer/desktop tooling, P2 desktop applications, P3 unrelated or educational references, and the supplemental set:
- `google-research/timesfm`, `47thtechcorner/RayCodes_TimesFM3.0`
- `tradesdontlie/tradingview-mcp`, `AI4Finance-Foundation/FinRL-Trading`, `OpenByteInc/QuantDinger`
- `Signal-Execution-Labs/forex-trading-ai-agent`, `BaggaT236/AI-Trading-Skills`, `simonlin1212/TradingAgents-astock`, `gr33njj/multi-setup-tradingview`
- Earlier requested tooling candidates including Codync, Qwen Code, Open Interpreter, OpenCode, Claude Code UI and related desktop/debugging/observability repositories.
- This latest batch: the four repositories listed in the table above.

Use the intake documents for per-repository initial findings. “In scope” means track and assess, not that all repositories should be cloned, installed or merged. Do not create one monolithic workspace containing every project. Clone only selected candidates into isolated, disposable workspaces after license and risk triage.

## Agent responsibilities and recommended tool permissions

### Claude / Claude Code — primary implementation and code-review lead
Allowed: repository read/write on the AURELIA review branch; targeted file edits; unit/integration test authoring; static analysis; dependency inventory; CI log review; isolated sandbox runs with no secrets; prepare small, reviewable PRs.
Required tools: GitHub repository/PR/workflow APIs; local shell and git only in a provisioned disposable workspace; Python test/lint/type-check/security tools; dependency lockfile/SBOM and secret scanning; container build/test in a non-production environment.
Forbidden: merge to `main` without approved review; alter release authority, risk limits, LIVE_LOCK or secrets; execute unknown setup scripts on the host; access production broker credentials; place live orders.

### ChatGPT — architecture, research and assurance coordinator
Allowed: maintain the intake ledger, map requirements to candidates, draft threat models and test plans, compare evidence, inspect GitHub source/CI metadata, and challenge conclusions independently.
Required tools: GitHub connector, web/documentation search, repository/file inspection, test/evidence review, issue/PR comments, and a structured evidence ledger.
Forbidden: claim a repo is installed without workspace evidence; fabricate test outcomes; treat model consensus or backtests as execution authorization; expose secrets in prompts.

### Grok — independent market/news and adversarial research analyst
Allowed: source-linked macro/news/sentiment summaries, candidate hypothesis generation, contradiction detection, and independent review of other agents' conclusions.
Required tools: source-attributed web/news access; read-only market data; reproducible research notebooks or isolated research jobs; citation/evidence capture.
Forbidden: broker credentials, order submission, editing the risk engine or live configuration, unsupported performance claims. Social posts are untrusted signals, not ground truth.

### JEV — deterministic QA, operations and evidence auditor
Allowed: run approved CI/assurance workflows, inspect logs, verify commit hashes, check evidence freshness/completeness, reproduce deterministic tests, maintain failure/rollback checklists, and report blockers.
Required tools: GitHub Actions/workflow logs; test runner and static checks in isolated workspace; deployment health/log read access only after provisioned; evidence schema validation; alerts/status reporting.
Forbidden: bypass failing gates, manufacture evidence, reset safety locks, access broker trading credentials, or promote a release autonomously.

### Specialist agents — narrow, least-privilege assignments
- Quant/forecasting: TimesFM and FinRL research abstractions; Python/pandas/numpy, scikit-learn, statistical baselines, walk-forward/OOS evaluation, leakage tests. Research data only.
- Strategy auditor: extract explicit rules from Trading_Algo and TradingView setups; implement independent deterministic versions; run unit tests, bar-close/no-lookahead checks, costs/slippage and regime splits.
- Security/AppSec: dependency/SBOM and license scans, secret scanning, static analysis, container scanning, install-script review, threat modeling. Read-only by default; remediation PRs only.
- Data/market analyst: read-only Deriv public market data and cited macro/news sources; timestamp/freshness checks and source provenance.
- UI/observability: Emmanuel dashboard and Conky as reference only; frontend lint/accessibility and sanitized mock data; no account API keys.
- Release/ops: JEV-owned evidence checklist and CI; production configuration changes require explicit human review and protected environment approval.

## Tool routing and governance
1. One issue/task per deliverable with owner, acceptance criteria, permitted tools, data classification, expected artifact and rollback.
2. Read-only discovery first. For each repo, inspect default branch, exact HEAD SHA, license, recent activity, dependency manifests, workflows, install scripts, secrets handling and execution paths.
3. Only then create a pinned, isolated checkout. Do not use floating `latest` dependencies in a production path.
4. Agent output must include source commit, changed paths, commands actually run, raw test results, security findings and remaining uncertainty.
5. Require a second agent to challenge the result. The implementing agent cannot self-approve its security/release changes.
6. Merge only through protected PR checks and authorized human review. The external repository is never a source of production secrets or authority.
7. Continue to report live trading as BLOCKED until existing AURELIA certification evidence and broker verification are complete.

## Current execution status
- [x] Remote README/license spot-check completed for the four newly supplied repositories.
- [x] Agent responsibility and least-privilege tool-routing plan recorded.
- [ ] Verify exact HEAD SHA, all dependency/workflow/install files, license provenance and security posture for every candidate.
- [ ] Provision a connected, isolated workspace with git/shell; clone only approved candidates at pinned commits.
- [ ] Assign concrete tasks through agent/task systems and verify each agent's actual tool permissions.
- [ ] Run candidate-specific tests and create evidence-backed integration PRs only where justified.
- [ ] Physically sync repository checkouts to each agent runtime; not yet verified or completed by this documentation change.


## Latest supplemental intake — ten MCP/developer tooling repositories (2026-10-12)
Detailed README-level triage, agent ownership, risk controls, and staged validation are recorded in [`docs/REPOSITORY_TRIAGE_MCP_TOOLING_2026-10-12.md`](REPOSITORY_TRIAGE_MCP_TOOLING_2026-10-12.md). The short version:
- Claude Code + Dev AI: inspect Copilot plugins; use `jscpd` as report-only duplication analysis; evaluate `jcodemunch-mcp` only after commercial-license clearance.
- JEV + Claude Code: sandbox `mcp-github-project-manager` with least-privilege scopes and human approval for writes; evaluate the official `github/github-mcp-server` as the single primary GitHub MCP.
- Grok: compare `mcp-omnisearch` and Kindly Web Search against existing search capabilities; pilot at most one at a time with no secrets in prompts/configuration.
- ChatGPT + Grok: optional `idea-reality-mcp` for product/tool novelty research only; it is not a trading signal validator and its README reports maintenance mode.
- Dev AI: `zed-mcp-server-github` is editor-specific; `idosal/git-mcp` is a documentation-context candidate requiring privacy and prompt-injection review.
- All 10 are **candidates**, not installations. External repositories are pull-only in the connected GitHub integration. Physical clones, agent-runtime configuration, and end-to-end operation remain unverified. No live-trading or capital authority changes are allowed.
