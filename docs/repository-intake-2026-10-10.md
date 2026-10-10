# External Repository Intake — 2026-10-10

## Purpose and status

This is an intake manifest for AURELIA's research and developer tooling. Recording a URL does **not** mean the project has been cloned, installed, security-reviewed, or integrated. All third-party repositories remain isolated research inputs until review is complete.

Canonical AURELIA repository: `Anto-30/aurelia-trading`
Target branch for this manifest: `research/repository-intake-2026-10-10`
Canonical production branch remains `main`. This intake does not authorize a merge to main, deployment, access to live credentials, or changes to risk/execution controls.

## Routing policy

- **Claude Code + ChatGPT:** coordinating reviewers; neither receives broker/capital authority through this intake.
- **Grok:** research triage, documentation and independent challenge of project claims; no production secrets.
- **JEV:** independent test/security/evidence review; no production secrets.
- **AURELIA research agents:** sandboxed experiments only. Strategy code must pass data provenance, out-of-sample, calibration, fees/slippage, risk and execution validation before a separate reviewed integration.
- Actual synchronization into Grok, JEV, Claude Code or ChatGPT workspaces is **pending**; this GitHub manifest alone does not provision those external workspaces.

## Required gates for every repository

1. Confirm repository identity, default branch, latest commit and maintenance status.
2. Record license and redistribution obligations.
3. Inspect install scripts, dependency manifests, network access, credential handling and supply-chain risks.
4. Clone/build/test in an isolated environment without live credentials.
5. Record reproducible test evidence and limitations.
6. Assign an owner and intended use; open a reviewed pull request for any AURELIA integration.
7. Never weaken account isolation, Risk Warden, Execution Firewall, kill switch, ledger/reconciliation, broker verification or release authority.

## Repository inventory

| Repository | Initial routing | Initial disposition |
|---|---|---|
| https://github.com/OpenSees/OpenSees.git | Research triage | Separate engineering simulation; not a default trading dependency |
| https://github.com/lidge-jun/opencodex.git | Claude Code / ChatGPT | Coding-tool review |
| https://github.com/alphaXiv/OpenResearch.git | Grok / research agents | Research workflow review |
| https://github.com/ferdikoomen/openapi-typescript-codegen.git | Developer tooling | API client generation; review before use |
| https://github.com/anymorph-ai/Claudable.git | Claude Code | Coding-tool and security review |
| https://github.com/kolevans/FreeClaudeCode.git | Security review | Do not use until provenance, license and provider terms are checked |
| https://github.com/tradytics/eiten.git | Quant research | Strategy/backtest review; no live execution |
| https://github.com/chrisconlan/algorithmic-trading-with-python.git | Quant research | Educational/reference code; validate methodology |
| https://github.com/letianzj/quanttrader.git | Quant research | Backtesting/execution assumptions review |
| https://github.com/carlvellotti/free-ai-courses.git | Agent training | Reference library only |
| https://github.com/je-suis-tm/quant-trading.git | Quant research | Strategy and dependency review |
| https://github.com/obra/superpowers.git | Claude Code / engineering | Workflow review |
| https://github.com/soongenwong/claudecode.git | Claude Code | Identity, provenance and security review |
| https://github.com/hkqr/my-free-code.git | Engineering triage | Inspect purpose before assignment |
| https://github.com/router-for-me/CLIProxyAPI.git | Model infrastructure | Authentication, logging, provider terms and secret handling review |
| https://github.com/codeaashu/free-claude-code.git | Security review | Do not use until provenance, license and provider terms are checked |
| https://github.com/freecodexyz/free-code.git | Engineering triage | Inspect purpose before assignment |
| https://github.com/siteboon/claudecodeui.git | Developer interface | UI and security review |
| https://github.com/decolua/9router.git | Model infrastructure | Authentication, logging and provider terms review |
| https://github.com/Rishurajgautam24/free-claude-code.git | Security review | Do not use until provenance, license and provider terms are checked |
| https://github.com/HKUDS/DeepCode.git | Coding agents | Code-analysis review |
| https://github.com/open-free-llm-api/awesome-freellm-apis.git | Model infrastructure | Provider privacy, reliability and rate-limit review |
| https://github.com/Alishahryar1/free-claude-code.git | Security review | Do not use until provenance, license and provider terms are checked |
| https://github.com/AIwithhassan/free-claude-code-setup.git | Security review | Setup scripts and credential handling review |
| https://github.com/ssmDo/CodeFreeMax.git | Engineering triage | Inspect purpose before assignment |
| https://github.com/AbuZar-Ansarii/Claude-Ollama-VScode.git | Local model tooling | Local inference and data-boundary review |
| https://github.com/matt1398/claude-devtools.git | Developer tooling | Inspect code and permissions |
| https://github.com/diegosouzapw/OmniRoute.git | Model infrastructure | Routing, auth, provider terms and logging review |
| https://github.com/getagentseal/codeburn.git | Security review | Verify provenance and security claims |
| https://github.com/Avijit07x/claude-db.git | Data/persistence review | Inspect schema, storage and secret handling |
| https://github.com/google/open-location-code.git | Optional utility | Geographic encoding; only if required by an approved feature |
| https://github.com/LING71671/Open-ClaudeCode.git | Claude Code | Provenance, license and security review |
| https://github.com/openmrs/openmrs-core.git | Separate project | Medical-records platform; exclude from AURELIA runtime |
| https://github.com/CodeEditApp/CodeEdit.git | Separate project | macOS editor; not a default trading dependency |
| https://github.com/chauncygu/collection-claude-code-source-code.git | Reference-only | Verify provenance and licensing; do not treat as official source |
| https://github.com/continuedev/continue.git | Coding agents | IDE/agent integration review |
| https://github.com/idosal/git-mcp.git | Repository intelligence | Read-only analysis first; scope permissions |
| https://github.com/ArtemXTech/claudecode-obsidian-starter.git | Documentation | Optional notes/workflow review |
| https://github.com/anomalyco/opencode.git | Coding agents | Agent capabilities, permissions and sandbox review |
| https://github.com/alibaba/open-code-review.git | Code review | Independent review workflow |
| https://github.com/Fission-AI/OpenSpec.git | Specifications | Specification-driven engineering review |
| https://github.com/freeCodeCamp/freeCodeCamp.git | Agent training | Educational reference; not a runtime dependency |
| https://github.com/PawanOsman/OpenCursor.git | Coding tools | Provenance, license and security review |
| https://github.com/OpenCoworkAI/open-codesign.git | Engineering triage | Inspect purpose and trust boundaries |
| https://github.com/codeigniter4/CodeIgniter4.git | Separate project | PHP framework; not a default AURELIA dependency |
| https://github.com/nexu-io/open-design.git | Design tooling | Separate workflow; not a trading dependency by default |
| https://github.com/openinterpreter/openinterpreter.git | Coding agents | High-permission execution risks; sandbox and approval gates required |
| https://github.com/oracle/opengrok.git | Repository intelligence | Code indexing/search review |
| https://github.com/VRSEN/OpenSwarm.git | Agent orchestration | Permissions, persistence and agent-boundary review |
| https://github.com/openframeworks/openFrameworks.git | Separate project | Creative-coding framework; not a default trading dependency |
| https://github.com/QwenLM/qwen-code.git | Coding agents | Corrected from malformed combined URL in intake message; inspect capabilities and permissions |
| https://github.com/codewhale-hq/Codewhale.git | Coding agents | Code workflow and security review |

## Quantitative research acceptance criteria

Any trading-related candidate must remain research-only until independently validated using reproducible data provenance, out-of-sample and multi-regime tests, calibrated probability estimates, costs/slippage, drawdown and risk limits, broker minimum-stake constraints, and verified paper execution. No strategy claim or repository README is qualification evidence by itself.

AURELIA's existing account isolation, deterministic risk checks, execution firewall, transaction verification, idempotency, reconciliation, kill switch and release authority remain mandatory. Low balance or broker uncertainty must continue to block orders.

## Current completion status

- Intake manifest: prepared for review on this branch.
- Repository clones/installations: not performed by this manifest operation.
- License/security reviews: pending.
- Agent workspace distribution to Grok, JEV, Claude Code and ChatGPT: pending; external workspace access is not implied by GitHub access.
- Production deployment/live trading authorization: unchanged and not authorized by this intake.
