# AURELIA four-agent federation: TradingView PDF adaptation (2026-10-12)

## Status and evidence boundary

This document adapts the uploaded **TradingView published .docx.pdf** (ZeroOne Systems, “Zero Human Trading Firm”) to AURELIA. It is an architecture proposal committed for review; it is not evidence that Claude Code, ChatGPT, Grok, or JEV are connected as persistent workers, that any external service is authenticated, or that live trading is qualified.

The source PDF describes a six-agent organization (CEO, Research, Backtest, Risk Management, Execution, Cost Optimizer), a Paperclip task/delegation loop, TradingView MCP for OHLCV, institutional-memory files, and a strategy gate based on Sharpe, drawdown, at least six months of backtest history, 30 days of paper trading, and explicit human/Board approval. It also includes setup scripts that persist an Anthropic API key and configure “dangerouslySkipPermissions: true”. Those implementation choices are source content, not AURELIA requirements.

## Design decision

Retain one canonical system: Anto-30/aurelia-trading, branch main, one capital plane, one release authority, and one evidence lineage. Do not create a parallel “trading firm,” duplicate strategy registry, independent execution engine, or second risk engine.

The PDF's six functions are useful as a responsibility model. They should be mapped onto the four requested agent profiles and existing deterministic AURELIA controls, not copied as six autonomous capital-capable agents.

## Four-agent responsibility map

| PDF function | Assigned profile | Allowed work | Explicit boundary |
|---|---|---|---|
| CEO / task router | **ChatGPT — supervisory planner** | Turn the objective into scoped tasks; choose tools available in the current session; reconcile reports; prepare a decision brief; track open blockers. | No claim of persistent worker availability unless independently verified; no production secrets, live-lock changes, or broker order submission. |
| Research Agent | **Grok — research and orchestration** | Discover candidate ideas and catalysts from public sources; retain source URLs, timestamps, assumptions, and counter-evidence; create a scored research brief; route tasks. | Public-source claims remain untrusted inputs. No order authority, no direct capital-plane access, no autonomous dependency installation. |
| Backtest Agent / implementation | **Claude Code — primary engineering agent** | Implement or repair research/backtest tooling on a branch; add tests; record data provenance, instrument, timeframe, costs, sample, out-of-sample split, and metrics; prepare minimal diffs. | No blanket permission bypass; no secret extraction; no direct release authorization. Local shell/device access is conditional on an actually connected and authorized runtime. |
| Risk Management Agent / independent reviewer | **JEV — independent assurance** | Independently inspect diffs, tests, look-ahead/data leakage, costs, calibration, evidence freshness, policy compliance, and release artifacts; issue PASS/FAIL/BLOCKED with cited evidence. | Reviewer sign-off is evidence only, not capital authorization. JEV must not modify the controls it evaluates or self-approve a release. |
| Execution Agent | **AURELIA's existing deterministic capital plane only** | Validate approved intents and, only through existing policy, account, risk, execution, transaction-verification, idempotency, and reconciliation gates, handle capital-moving actions. | Not delegated to Claude, ChatGPT, Grok, JEV, Paperclip, TradingView MCP, or a third-party model. |
| Cost Optimizer | **ChatGPT reports; owner-approved engineering changes only** | Summarize token/tool spend where actual usage data is available; recommend model/tool routing and caching; estimate trade-offs. | No invented usage numbers, no silent model-policy changes, no permission weakening, no production setting changes without review. |

The existing role registry in config/agent_tool_skill_assignment.json already describes Claude Code as primary engineering, Grok as orchestration, JEV as validation, and ChatGPT as supervisory. This document makes the PDF-to-AURELIA mapping explicit; it does not claim those profiles are runtime connections.

## Operating protocol

1. **Intake and task contract (ChatGPT).** State the requested outcome, canonical branch/commit, files in scope, acceptance tests, data needs, security boundary, independent reviewer, and what evidence would falsify completion.
2. **Source collection (Grok).** Deliver a research brief with source URL, retrieval timestamp, market/instrument, exact claim, assumptions, novelty/feasibility/edge scores, counter-evidence, and proposed next experiment. Do not treat likes, social engagement, or model confidence as proof of edge.
3. **Implementation and quant validation (Claude Code).** Work on a feature branch. Use reproducible data snapshots; document entry/exit rules, instrument, timeframe, spread/fees/slippage, sample size, train/validation/test periods, and all metrics. Keep historical runs append-only rather than overwriting prior evidence. Do not promote a strategy based on a single Sharpe/drawdown threshold alone.
4. **Independent review (JEV).** Verify exact commit, diff, tests, evidence references, no look-ahead bias, survivorship/data-selection risks, realistic costs, calibration and regime coverage. Return PASS, FAIL, or BLOCKED; missing, stale, contradictory, or unverifiable evidence is BLOCKED.
5. **Deterministic release gate (AURELIA).** Only the existing readiness and release pipeline may evaluate the whole evidence set. Passing agent review, CI, a TradingView chart, or a paper-trading result is not live authorization.
6. **Owner-facing synthesis (ChatGPT).** Report verified changes separately from recommendations, list exact commit/PR/test evidence, and enumerate blockers and owner-only steps.

## Evidence artifact contract

Every material task should produce a record containing:
- task ID, responsible agent, reviewer, UTC timestamps, repository, branch, exact commit SHA, and changed paths;
- source/data URL or dataset identity, retrieval time, instrument, timeframe, sample period, and any known limitations;
- hypothesis and rules before testing; train/validation/out-of-sample split; costs and execution assumptions;
- sample size, trade count, expectancy/net EV, Sharpe, max drawdown, win rate, calibration and uncertainty where applicable;
- command/test names, exit status, CI run URL, report/artifact links, reviewer result, and unresolved findings;
- explicit state: RECOMMENDATION_ONLY, RESEARCH_ONLY, SANDBOX_ONLY, PAPER_ONLY, BLOCKED, or a state assigned by the existing release process. Agents must not mint a live-authorized state.

Use existing AURELIA evidence and strategy registries wherever possible. Do not create a competing institutional-memory source of truth or infer broker state from local logs.

## Strategy qualification: source rule versus AURELIA rule

The PDF's six-month backtest, Sharpe/drawdown floor, 30-day paper-trading period, and human approval are source-specific heuristics. They are not sufficient proof of robust profitability and must not replace AURELIA's current instrument-specific qualification, prospective out-of-sample evidence, calibration, execution economics, soak, broker lifecycle verification, account/balance truth, reconciliation, and release gates. Do not copy numeric thresholds from the PDF without an explicit policy review and tests.

For any strategy candidate, require reproducible rules, sufficient instrument-specific history, out-of-sample and forward/paper evidence, realistic costs, net positive expectancy with uncertainty assessed, risk limits, and a documented reason to reject as well as accept. A synthetic index or tick strategy must not borrow FX/equity assumptions or unverified order-book data.

## Security review of the PDF's setup pattern

Do **not** copy these source-script behaviors into a production environment:
- “dangerouslySkipPermissions: true” as a blanket agent setting. Prefer scoped tools, human approval for consequential operations, isolated worktrees/sandboxes, and explicit command allowlists.
- Pasting an API key into a prompt, shell command, source file, profile file, logs, or shared agent context. Use the approved secret store and least-privilege credentials; rotate any value that may have been exposed.
- Giving every specialist a shared Anthropic secret or broad filesystem/shell access by default. Scope credentials and filesystem access per agent and task.
- Treating a Paperclip API task completion, a local “all agents verified” message, or a TradingView MCP response as broker or release evidence.
- Letting a model agent modify risk thresholds, live locks, final authorization flags, account bindings, or execution controls.

Paperclip can be considered only as an optional task-management surface after a separate threat model and integration review. Its adoption is not required to implement this responsibility model and must not introduce a second release authority.

## Acceptance checklist for a future implementation

- [ ] Existing canonical role registry remains the single role/tool assignment source; no duplicate engine or registry.
- [ ] Role routes distinguish advisory/research/engineering/review from capital-plane authority.
- [ ] External research and tool outputs are stored as untrusted, source-linked evidence.
- [ ] Agent tasks are branch-scoped; all policy or code changes receive independent review.
- [ ] No agent has authority to alter config/LIVE_LOCK.yaml, final execution authorization, account binding, or risk policy.
- [ ] External LLMs and tools cannot read production credentials or submit broker transactions.
- [ ] Release gate fails closed on missing/stale/contradictory evidence.
- [ ] Automated tests cover role boundaries, task routing, untrusted source handling, and prohibited capital actions.
- [ ] Current CI and exact-commit assurance evidence are reviewed before merge.
- [ ] Persistent worker/runtime connections are verified separately; a role entry in JSON is not proof of a running agent.

## Verified state at time of drafting

- The GitHub connector successfully read Anto-30/aurelia-trading metadata and the main README; repository-level read/write permission was reported for this engineering integration.
- The README identifies config/agent_tool_skill_assignment.json as the existing task-aware role/tool/skill registry and says that registry membership does not prove that a plugin is installed or connected.
- The README and docs/MOBILE_ONLY_DEVELOPMENT_AND_DEPLOYMENT.md state that production remains fail-closed and that prior assurance output was CERTIFICATION_RESULT=NOT_READY, FINAL_EXECUTION_AUTHORIZATION=FALSE, and LIVE_EXECUTION=BLOCKED, with authenticated Deriv lifecycle and other qualification evidence missing in that recorded run.
- This document is an architecture artifact only. No runtime agent was connected, no production secret was read, no live order was submitted, and no live-readiness claim is made by this document.

## References

- Uploaded source: *TradingView published .docx.pdf*, ZeroOne Systems, “I Built a Zero-Human Trading Team with Claude” setup material (conversation attachment).
- Existing role/tool registry: ../config/agent_tool_skill_assignment.json
- Canonical system overview: ../README.md
- Operational and deployment limitations: MOBILE_ONLY_DEVELOPMENT_AND_DEPLOYMENT.md
- Live release control: ../config/LIVE_LOCK.yaml
