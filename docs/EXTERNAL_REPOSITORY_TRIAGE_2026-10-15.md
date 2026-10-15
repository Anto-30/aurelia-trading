# External Repository Intake — 2026-10-15

## Scope and status

This document records an initial triage of the 18 unique upstream repositories supplied on 2026-10-15 (19 URLs were supplied because `langchain-ai/agent-inbox` was duplicated). This is not a source-code security audit, dependency/SBOM/CVE scan, legal opinion, compatibility certification, strategy qualification, or approval to install or execute any project.

**No repository in this list is approved for production use.** Do not clone-and-run untrusted code on a host with AURELIA, Deriv, SSH, cloud, GitHub-write, or other production credentials. Do not grant external projects access to AURELIA's capital plane, broker session, live lock, ledger, or production secret store.

## Initial triage

| Repository | Potential relevance | Initial disposition and required checks |
|---|---|---|
| https://github.com/cuemacro/findatapy | Financial/FX/economic market-data research ingestion | Research candidate. Inspect data-provider licenses, source terms, point-in-time semantics, dependency locks, and data-quality behavior. Not a Deriv adapter. |
| https://github.com/anthropics/claude-plugins-official | Claude Code plugin/skill ecosystem | Tooling reference. Review each plugin separately for permissions, scripts, MCP endpoints, secret access, network egress, and license. Repository inclusion is not blanket approval. |
| https://github.com/ZhuLinsen/daily_stock_analysis | Scheduled equity analysis/reporting | Research/reporting reference. Equity data and signals do not establish suitability for Deriv synthetic indices. Audit data licensing and scheduler/network behavior. |
| https://github.com/jo-inc/camofox-browser | Browser automation for agent workflows | Sandbox-only candidate. Inspect browser isolation, session/cookie handling, remote endpoints, filesystem permissions, and prompt-injection exposure. Never expose production sessions. |
| https://github.com/The-Swarm-Corporation/AutoHedge | Multi-agent/crypto trading concepts | Reference-only pending source audit. Confirm supported venue, capital/execution boundary, dependency provenance, and license. No agent may authorize AURELIA capital. |
| https://github.com/kgeoffrey/AutoHedge.jl | Julia options/hedging and quantitative research | Research-only reference. Check mathematical assumptions, instrument model, tests, and license; options Greeks/hedging are not directly transferable to Deriv synthetic contracts. |
| https://github.com/charlesaurav13/AutoHedge | Trading/hedging bot concepts | Unverified candidate. Confirm repository status, immutable commit, license, broker/API behavior, dependencies, and tests before further assessment. |
| https://github.com/charlesaurav13/autohedge-trading-bot | Automated trading/RL concepts | Research-only. Require leakage-safe walk-forward/OOS tests, calibration, cost modeling, drawdown controls, and source-level execution audit. |
| https://github.com/HKUDS/Vibe-Trading | AI-assisted trading research/backtesting | Research-only, isolated sandbox required. Inspect generated-code execution, subprocess/network permissions, leakage controls, and backtest fill assumptions. Never run generated strategies with secrets. |
| https://github.com/OpenByteInc/QuantDinger | Trading research/backtesting/platform architecture | Architecture reference only. Avoid importing a second trading engine. Review license, dependencies, execution adapters, and boundaries between research, risk, and execution. |
| https://github.com/simonlin1212/Vibe-Research | AI research workspace and information synthesis | Optional research tooling. Review external data transfer, provider credentials, persistence, and evidence provenance. Must not become the authoritative ledger or release authority. |
| https://github.com/VibeTradingLabs/vibetrading | Python trading strategy generation/backtesting | Research-only. Verify supported exchanges, runtime isolation, license, and reproducibility; do not infer Deriv compatibility from generic exchange adapters. |
| https://github.com/hopit-ai/india-trade-cli | India-market/trading CLI workflows | Low-priority reference until exact broker, instrument, data, and licensing scope is verified. Not presumed compatible with Deriv. |
| https://github.com/Fincept-Corporation/FinceptTerminal | Financial terminal, analytics, and data aggregation | Dashboard/analytics reference. Review license obligations (including copyleft implications), provider terms, embedded credentials, and network behavior before any code reuse. |
| https://github.com/langchain-ai/agent-inbox | Agent task handoff/inbox patterns | Workflow reference. Evaluate authentication, authorization, persistence, and human approval support. Must not grant agent messages capital authority. |
| https://github.com/Gaurav-Gosain/tuios | Terminal/UI tooling | Low-priority operator-interface reference. No production adoption without dependency/license review and confirmation it solves a concrete operational requirement. |
| https://github.com/cloudflare/agentic-inbox | Agent communication/workflow patterns | Compare with other inbox options; select at most one if a real gap exists. Review deployment model, identity, permissions, and data retention. |
| https://github.com/mikecann/agent-inbox | Agent inbox/workflow patterns | Compare with LangChain and Cloudflare alternatives; avoid redundant orchestration components. Review source provenance, authentication, and message trust boundaries. |
| https://github.com/pizza-bot-app/pizza-bot | Apparently unrelated bot/application | Defer. Revisit only if source inspection demonstrates a specific reusable component relevant to AURELIA. |

## Required verification before any adoption

For each candidate selected for deeper review:

1. Record canonical repository URL, default branch, exact immutable commit SHA, archive/maintenance status, and retrieval timestamp.
2. Read the actual LICENSE and relevant subdirectory licenses; do not infer a license from a README badge or a parent/catalog repository.
3. Inspect manifests, lockfiles, installation/build scripts, CI workflows, release provenance, security policy, and available advisories.
4. Generate an SBOM and scan direct/transitive dependencies in a disposable, credential-free environment. If the scanner or advisory endpoint is unavailable, record **NOT SCANNED**, never “zero vulnerabilities.”
5. Review source for secret access, subprocess execution, dynamic code loading, filesystem access, telemetry, network egress, browser/session access, and unsafe deserialization.
6. Run tests in an isolated runner without production credentials or write permissions to the canonical AURELIA repository/configuration. Capture exact commit and logs.
7. Document the narrow reusable interface, integration tests, rollback plan, license decision, and independent reviewer.
8. For any strategy/research component, separately validate point-in-time data, no lookahead, prefix stability, transaction costs, calibration, drift, and prospective out-of-sample economics. A green CI run is not evidence of a profitable strategy.

## AURELIA integration boundary

External repositories may inform Layer 9 research, historical data preparation, testing, dashboards, or agent coordination. They must not replace the canonical AURELIA runtime, Layer 6 deterministic risk engine, capital plane, Deriv broker-verification path, execution firewall, ledger/reconciliation, or release authority. LLMs and external agents may propose work but cannot enable live trading or bypass fail-closed controls.

Preserve `VERIFY_ONLY`, `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and the checked-in live lock until all existing independent production gates have fresh evidence and authorized review. This intake document does not change any secret, environment, deployment, live lock, or capital setting.

## Suggested order of deeper review

1. `findatapy` — market-data research utility, only after checking source/provider terms.
2. `Vibe-Trading` and `VibeTradingLabs/vibetrading` — compare backtest methodology and generated-code isolation.
3. `QuantDinger` — architecture comparison only; do not introduce a second engine.
4. One agent-inbox option at most — choose based on a demonstrated operational gap.
5. Claude plugins and browser automation — per-plugin/per-tool permission and egress review before enabling.
6. Remaining candidates — defer until a concrete use case justifies audit effort.

This is a triage record, not a statement that any candidate passed the checks above.
