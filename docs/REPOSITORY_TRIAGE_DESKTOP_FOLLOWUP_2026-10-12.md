# Repository and Desktop Access Follow-up — 2026-10-12

## Status and scope

This is a research-only follow-up to the repository intake. No external project has been installed into the production runtime, no external repository has been merged into `main`, and no live-trading gate has been relaxed.

## Desktop/agent access diagnosis

The connected Desktop Commander account authenticates successfully, but its device inventory returns **zero connected devices**. Therefore this session cannot inspect, clone, modify, or execute commands on the user's desktop through Desktop Commander yet. This is a pairing/availability blocker, not a demonstrated bug in AURELIA itself.

Official setup reference: https://github.com/desktop-commander/remote-desktop-commander/blob/main/docs/SETUP.md

On the target computer:
1. Ensure Node.js 18 or newer is installed (`node --version`).
2. Open a terminal on that computer and run `npx @wonderwhy-er/desktop-commander@latest remote`.
3. Complete the browser device authorization and confirm the code displayed in the browser matches the code printed in that terminal.
4. Keep the terminal process running; the remote device disconnects when it stops.
5. Confirm the machine appears online in the Desktop Commander device dashboard, then retry device listing/ping from this session.

Do not paste pairing codes, session files, API tokens, private keys, or other credentials into chat. If the command errors, capture only the non-secret error text and version/platform details.

## Additional repository README triage

The following public repository metadata and README files were accessible during this pass. These are classification signals only; no code was cloned, executed, or dependency-audited in this pass.

| Repository | README-level purpose | Preliminary disposition |
|---|---|---|
| `siteboon/claudecodeui` | Desktop/mobile UI for Claude Code, Cursor CLI and Codex; local or remote project/session access | Candidate for agent UX; inspect authentication, network exposure, telemetry and permissions before use |
| `leepokai/Codync` | Open-source desktop application that lets users message coding agents as teammates; README advertises Windows/macOS/Linux builds | Candidate for agent workflow UX; verify release provenance, update mechanism, credential storage and license before installing |
| `QwenLM/qwen-code` | Open-source coding agent for terminal, editor, desktop, browser and chat; README indicates Node.js >=22 | Research/agent tooling candidate; evaluate as an optional specialist, not a change to the selected primary-agent architecture |
| `openinterpreter/openinterpreter` | Coding agent optimized for lower-cost models; README advertises Apache-2.0 licensing | Research-only candidate; review current architecture, tool permissions and execution sandbox before enabling |
| `anomalyco/opencode` | Open-source AI coding agent; repository default branch is `dev` | Candidate for isolated evaluation; pin an immutable commit and inspect the actual license and release provenance |
| `google-github-actions/auth` | GitHub Action for Google Cloud authentication; README recommends Workload Identity Federation over long-lived service-account keys | CI identity reference only; not a desktop repair tool and not a replacement for AURELIA's protected deployment credentials |
| `goauthentik/authentik` | Identity-provider platform | Out of scope for immediate desktop diagnosis unless AURELIA needs a separately approved identity service |
| `better-auth/better-auth` | TypeScript authentication/authorization framework | Application-layer reference only; no integration justified by the current desktop connectivity evidence |
| `railwayapp/cli` | Railway CLI | Reference only until the deployment target is explicitly confirmed; current handoff notes say Railway is not the active deployment path |

Other metadata lookups confirmed public repositories and default branches for these candidates, but that is not proof of safety, maintenance quality, compatibility, or license compliance.

## AURELIA CI evidence observed

For PR #119 at commit `aa177d88cf9fb33b0e16b4aaa121d7e73aa5ca67`, the agent-federation audit (run 38272112632) and continuity watchdog (run 38272112390) completed successfully. AURELIA Assurance (run 38272112360) subsequently completed successfully at the workflow level. Compilation, static production acceptance audit, deployment/secret-script syntax validation, research tests, assurance tests, runtime tests, secret-presence tests, hardening tests, container build, public Deriv transport, worker health and the fail-closed gate checks passed. Authenticated Deriv real-account session, read-only account evidence and verify-only lifecycle steps were skipped because `DERIV_AUTH_CONFIGURED=false`. The certification output explicitly reports `CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=FALSE`, and `LIVE_EXECUTION=BLOCKED`. Missing required evidence artifacts: `evidence/broker_lifecycle.json`, `evidence/recovery_matrix.json`, `evidence/soak_3600s.json`, `evidence/prospective_oos.json`, `evidence/calibration.json`, `evidence/execution_economics.json`, `evidence/security_audit.json`, `evidence/deployment.json`, and `evidence/strategy_eligibility.json`. These are genuine evidence gaps, not CI software-test failures; do not synthesize or fabricate them to satisfy certification.

The PR's combined commit-status endpoint returned no external status entries; this must not be interpreted as proof that all required checks passed.

## Acceptance conditions before adopting any repository

- Pin a reviewed immutable commit; record upstream URL, license, release status, maintenance signals and dependency inventory.
- Inspect install scripts, lifecycle hooks, network calls, credential handling, filesystem scope and execution permissions.
- Run dependency/security and tests in an isolated disposable environment with no production secrets and no broker trading permissions.
- Keep all findings and integration changes on a review branch; use a separate reviewed PR for each actual code integration.
- Preserve the single canonical AURELIA engine, capital plane, release authority and evidence lineage. External agents and research tools must not gain capital authority.
- Do not change `LIVE_LOCK`, bypass the Risk Warden/execution firewall, or authorize live orders based on CI success alone.


## Public metadata and license pass

Repository metadata was queried on 2026-10-12. `pushed_at` is an upstream activity signal, not proof that a release is secure or production-ready.

| Repository | Declared SPDX license | Last push observed (UTC) | Preliminary decision |
|---|---|---:|---|
| `siteboon/claudecodeui` | AGPL-3.0 | 2026-10-12 | Do not deploy into a proprietary hosted product until AGPL obligations and remote-session security are reviewed |
| `leepokai/Codync` | Apache-2.0 | 2026-10-12 | Highest-priority desktop/agent UX candidate for isolated evaluation; still requires threat-model, dependency and installer review |
| `yeshrajawat/codync` | No license declared by GitHub API | 2022-06-03 | Reject as an install candidate unless ownership, provenance, maintenance and license are clarified; treat as stale/duplicate relative to the actively updated Codync project |
| `QwenLM/qwen-code` | Apache-2.0 | 2026-10-12 | Candidate for isolated specialist-agent evaluation; do not alter AURELIA's primary-agent configuration automatically |
| `openinterpreter/openinterpreter` | Apache-2.0 | 2026-10-11 | Research-only; requires strict tool-execution sandbox and permission review |
| `anomalyco/opencode` | MIT | 2026-10-12 | Candidate for isolated agent workflow evaluation; pin commit and inspect plugins/extensions before use |
| `jesse-ai/jesse` | MIT | 2026-10-12 | Research/backtesting reference only; crypto execution model is not automatically compatible with Deriv Options |
| `hummingbot/hummingbot` | Apache-2.0 | 2026-10-06 | Research/exchange-adapter reference only; architecture and venue assumptions differ from AURELIA's Deriv capital plane |
| `Drakkar-Software/OctoBot` | GPL-3.0 | 2026-10-12 | Do not embed into a proprietary distribution without GPL compatibility review; research-only until reviewed |
| `ccxt/ccxt` | MIT | 2026-10-12 | General exchange API reference; it does not replace the Deriv-specific broker adapter or source-of-truth checks |
| `bmoscon/cryptofeed` | NOASSERTION | 2026-10-10 | No clear SPDX license was returned; do not adopt until license is verified from the repository's license files |
| `google-github-actions/auth` | Apache-2.0 | 2026-07-29 | CI identity reference only; use workload identity federation rather than introducing long-lived service-account keys |
| `railwayapp/cli` | MIT | 2026-10-12 | Reference only; no deployment action taken because the current handoff identifies a different active deployment path |

These are preliminary screening outcomes, not full license opinions, dependency scans, code reviews, or runtime tests. No candidate was cloned or installed. Repository default branches and metadata can change; adoption decisions must pin exact commits and review the actual license text at that commit.


## Follow-up: completed baseline CI run

AURELIA Assurance run [38271166786](https://github.com/Anto-30/aurelia-trading/actions/runs/38271166786) completed successfully for commit `95ee60dd1ee65c4ae10503ddf84d6b2e3354eb8a`. All listed software tests, container build, public Deriv market-data transport check, readiness report, worker health check and fail-closed release-gate check passed in that run.

That successful repository CI run does **not** qualify live execution. The same run reported `DERIV_AUTH_CONFIGURED=false`; authenticated real-account session, broker-account and verify-only transaction lifecycle steps were skipped. The readiness report returned `final_execution_authorization=false` and `live_execution=BLOCKED`, and the worker health check reported `DEGRADED` with `CONTINUOUS_RUNTIME_UNAVAILABLE`. The run also reported the legacy Railway path as `NOT_CONFIGURED`.

Latest exact-head verification (2026-10-12): branch head `d6c490994e658fd89ad22c6e7d4de5d562ebf96a` was verified by AURELIA Assurance push run [38275087510](https://github.com/Anto-30/aurelia-trading/actions/runs/38275087510) and pull-request run [38275094620](https://github.com/Anto-30/aurelia-trading/actions/runs/38275094620); both workflow conclusions were `success` for that exact commit. The tests/build and fail-closed assertions passed, but the generated certification remains `NOT_READY`: `DERIV_AUTH_CONFIGURED=false`, authenticated account/lifecycle checks were skipped, required production evidence is missing, continuous runtime is unavailable, and `FINAL_EXECUTION_AUTHORIZATION=false` / `LIVE_EXECUTION=BLOCKED`. Workflow success is not production approval.


## Additional quant and trading-repository screen

| Repository | Metadata / README evidence | Preliminary disposition |
|---|---|---|
| `blampe/IbPy` | Archived; GitHub API returned `NOASSERTION` for license; README says the official Interactive Brokers Python API makes this project largely superfluous except for legacy Python 2 | Reject for new work; do not introduce an archived legacy broker adapter |
| `QuantConnect/Tutorials` | Apache-2.0; Jupyter/WordPress tutorials for LEAN and financial concepts; last push observed 2025-07-28 | Educational/research reference; not a drop-in AURELIA runtime or Deriv adapter |
| `cuemacro/finmarketpy` | Apache-2.0; market analysis, backtesting templates, seasonality and event-study utilities; last push observed 2026-04-16 | Research-plane candidate only; inspect dependency health and validate all results against AURELIA's independent backtest protocol |
| `SockTrader/SockTrader` | GPL-3.0; crypto trading bot; last push observed 2023-12-01 | Reject as an embedded component without GPL review; age and venue assumptions make it a low-priority reference |
| `mapalochuka81-spec/chuka-ai-trading-bot` | MIT; README makes broad production-ready claims and lists Deriv, Weltrade, Exness and MT5; last push observed 2026-08-24; only one star at metadata check | Do not trust claims without source-level verification; review broker credential handling, order path, minimum-stake rules, duplicate protection, transaction verification and reconciliation before any sandbox execution |
| `hyperliquid-dex/hyperliquid-python-sdk` | MIT; official-style Python SDK for Hyperliquid API trading; last push observed 2026-06-04 | Out of AURELIA's immediate Deriv scope; research reference only unless a separately approved Hyperliquid venue adapter is planned |

A missing or unclear license, an archived repository, or a low activity signal is grounds to defer adoption—not a reason to bypass legal or security review. No trading bot from this list is approved for live execution.


## Supplemental repository triage — 2026-10-12

This is a preliminary README and license spot-check, not a full security audit or local test. The duplicate RayCodes URL was counted once.

| Repository | Initial finding | Disposition |
|---|---|---|
| `google-research/timesfm` | Code license Apache-2.0. Upstream README says TimesFM 3.0 weights have a separate non-commercial license, unlike earlier checkpoints. | Priority forecasting research. Check the exact checkpoint license for intended use; evaluate with rolling-origin OOS data and simple baselines. |
| `47thtechcorner/RayCodes_TimesFM3.0` | README shows an Apache badge, but no top-level LICENSE file was found in the checked branch. | Reference-only until a license is verified. The upstream checkpoint terms still apply. |
| `tradesdontlie/tradingview-mcp` | MIT license. Local TradingView Desktop bridge using Chrome DevTools Protocol and undocumented internal APIs. | P1 chart/Pine workflow reference only. Requires a desktop and review of local debugging-port exposure; not a phone-only desktop replacement. |
| `AI4Finance-Foundation/FinRL-Trading` | Apache-2.0. FinRL-X research and trading infrastructure. | P0 research reference. Reproduce backtests with strict temporal splits, realistic costs and independent baselines. Do not replace AURELIA's capital plane. |
| `OpenByteInc/QuantDinger` | Apache-2.0. Self-hosted platform covering AI strategy generation, backtesting, paper/live execution and monitoring. | High-risk architecture reference only; review authentication, secrets, generated code and execution paths before isolated evaluation. |
| `Signal-Execution-Labs/forex-trading-ai-agent` | MIT license. README indicates a different maintainer/fork lineage. | Defer pending upstream identity and source-lineage review; inspect installation, dashboard, credential and order-flow behavior. |
| `BaggaT236/AI-Trading-Skills` | MIT license. TypeScript CLI and skill/workflow catalog; README quick-start clones a differently named repository. | P1 workflow reference. Resolve provenance and inspect every script/workflow before reuse. |
| `simonlin1212/TradingAgents-astock` | Apache-2.0. Research/educational multi-agent framework specialized for China A-shares. | Architecture reference only; its market rules and data vendors are not directly portable to Deriv. |
| `gr33njj/multi-setup-tradingview` | README describes Wyckoff, Quasimodo, intraday and liquidity setups; no top-level LICENSE file found. | Reference-only until permissions and exact rules are verified; independently test for repainting and look-ahead bias. |

### Recommended evaluation sequence
1. Resolve TimesFM 3.0 checkpoint licensing before choosing a deployment path; compare forecasts with naive/statistical baselines and rolling-origin evaluation. Forecast accuracy alone does not establish a trading edge.
2. Review FinRL-X and TradingAgents-Astock for research abstractions only; preserve AURELIA's existing strategy registry, risk engine, broker truth and release authority.
3. Review TradingView MCP and skills workflows for local access, command scope and provenance in an isolated environment.
4. Defer QuantDinger and the forex agent until source-level architecture and execution-path reviews are complete. Do not provide real broker credentials during intake.
5. Do not copy the multi-setup script until its license is verified. Convert any candidate rules into explicit testable hypotheses and require costs-aware out-of-sample evidence.

No repositories were cloned, installed or executed during this pass. No production secrets were used and no strategy was enabled.
