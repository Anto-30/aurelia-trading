# External Trading Repository Intake — 2026-11-05

## Decision

No external trading framework, broker adapter, autonomous trader, GPU unlocker, or model runtime from the supplied list is installed into the AURELIA production/runtime path by this change. This is intentional. The repositories span incompatible markets, broker APIs, licences, languages, runtime assumptions, and execution models. README claims are not security review, strategy evidence, or deployment approval.

A model-agnostic AURELIA intake skill has been added at `.agents/skills/aurelia-trading-repo-intake/SKILL.md`. It applies to every agent that works in this repository. It defines mandatory provenance, licence, dependency, security, isolation, testing, reviewer, and rollback gates. It does not make unconnected agents or plugins available.

## Candidate disposition

| Repository | Initial disposition | AURELIA relevance / blocking concern |
|---|---|---|
| `Mathieu2301/TradingView-API` | REFERENCE_ONLY | Community/unofficial TradingView client. README explicitly says it is not an official API. Auth/session and terms review required; not a production data source. |
| `simonlin1212/TradingAgents-astock` | REFERENCE_ONLY | A-share-specialized multi-agent research fork; market rules/data are not Deriv synthetic indices. README claims Apache-2.0; verify actual licence and upstream diff before reuse. |
| `stefan-jansen/machine-learning-for-trading` | RESEARCH_ONLY | Strong research education/reference; inspect each notebook/data dependency and adapt only methodology with reproducible, no-lookahead tests. |
| `marketcalls/openalgo` | SANDBOX_ONLY | Full platform with 36 broker integrations, strategy host, Flow, AI agent and order-capable API. Must not introduce a parallel capital/execution plane. |
| `hummingbot/hummingbot` | REFERENCE_ONLY / SANDBOX_ONLY | Apache-2.0 bot framework with venue connectors and execution lifecycle. Useful adapter/test concepts only; no live integration. |
| `kernc/backtesting.py` | RESEARCH_ONLY | Lightweight Python backtesting library; useful for isolated comparison, but validate fill model, spread, slippage, fees, intrabar assumptions and data leakage. |
| `NoFxAiOS/nofx` | SANDBOX_ONLY | AGPL-3.0 self-hosted trading system with continuous autopilot and exchange accounts. Strong copyleft and independent execution plane; do not vendor. |
| `ricequant/rqalpha` | NOT VERIFIED | README path returned 404 during this pass; identity/version/licence not yet verified. |
| `coding-kitties/investing-algorithm-framework` | REFERENCE_ONLY | Apache-2.0 strategy/backtest/deploy framework; verify broker/runtime model and dependencies before any reuse. |
| `paperswithbacktest/awesome-systematic-trading` | REFERENCE_ONLY | Curated resource list, not a software dependency; review individual linked projects separately. |
| `je-suis-tm/quant-trading` | REFERENCE_ONLY | Research scripts explicitly assume frictionless trades/no slippage/no surcharge/no illiquidity; unsuitable as direct strategy evidence. |
| `tradesdontlie/tradingview-mcp` | SANDBOX_ONLY | Controls local TradingView Desktop over CDP and uses undocumented internal APIs; desktop session, debug-port, subscription and security review required. |
| `pst-group/pysystemtrade` | REFERENCE_ONLY / SANDBOX_ONLY | Futures framework with Interactive Brokers integration; different market and execution model. No Deriv adapter reuse without isolated design. |
| `nautechsystems/nautilus_trader` | REFERENCE_ONLY / SANDBOX_ONLY | Rust/Python event-driven trading engine. Potential architecture/performance reference, but major runtime footprint and independent execution stack. |
| `endless-sky/endless-sky` | EXCLUDE | Space exploration game; unrelated to AURELIA. |
| `HKUDS/AI-Trader` | REFERENCE_ONLY / SANDBOX_ONLY | Agent-native trading platform; its README invites agents to register with a remote platform. No account registration or external execution. |
| `OpenByteInc/QuantDinger` | SANDBOX_ONLY | Self-hosted AI quant platform covering research through paper/live execution; separate product/runtime and deployment surface. |
| `StockSharp/StockSharp` | REFERENCE_ONLY / SANDBOX_ONLY | Broad .NET trading platform and connector ecosystem; not a Python/Deriv drop-in. |
| `QuantConnect/Lean` | NOT VERIFIED | README retrieval failed in this pass; do not infer current API, licence, or compatibility. |
| `freqtrade/freqtrade` | REFERENCE_ONLY / SANDBOX_ONLY | Python crypto bot with backtesting, dry-run and exchange integrations. Market/venue assumptions differ; keep out of AURELIA execution. |
| `Superalgos/Superalgos` | REFERENCE_ONLY | Community-owned social trading platform; token/community model and independent runtime are not required by AURELIA. |
| `TauricResearch/TradingAgents` | RESEARCH_ONLY | Apache-2.0 multi-agent financial research framework. Candidate for research orchestration patterns only; LLM outputs remain non-authoritative. |
| `hsliuping/TradingAgents-CN` | EXCLUDE from code import | Hybrid licence: Apache-2.0 core plus proprietary/source-available application layer; A-share-specific. |
| `Superior-Trade/superior-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT skills, but tied to Superior Trade Unified API, Hyperliquid/Lighter/Polymarket and deployment. Extract only generic, independently reviewed research guidance; no API endpoints, account flows or execution skills. |
| `Senpi-ai/senpi-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT skills for Hyperliquid-specific autonomous trading harness. Do not import account, sizing, deployment or execution procedures. |
| `ml4t/skills` | SKILL_ONLY candidate | Apache-2.0; 61 skills covering leakage, lookahead, cross-validation, transaction costs, and research-to-production workflow. Strong candidate for a curated, attribution-preserving subset after exact skill paths and tests are reviewed. |
| `alpacahq/alpaca-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | Apache-2.0 but Alpaca-specific; includes account onboarding, money movement and order placement. Exclude all broker-action skills from AURELIA agents. |
| `trading212-labs/agent-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT but Trading 212 API beta; includes order placement and account/portfolio operations. Not relevant to Deriv. |
| `JoelLewis/finance_skills` | REFERENCE_ONLY / SKILL_ONLY candidate | 91 Claude finance skills; licence and individual skill content not yet inspected. |
| `marketcalls/vectorbt-backtesting-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | VectorBT backtesting skill collection. Licence not confirmed in this pass; market/fee assumptions and generated code need audit. |
| `ginlix-ai/LangAlpha` | REFERENCE_ONLY / SANDBOX_ONLY | Apache-2.0, Python 3.13+, LangChain-based agentic trading harness. Has brokerage-account permissions; do not connect it to AURELIA capital. |
| `MobiusQuant/OpenMobius-skill` | SKILL_ONLY candidate | Apache-2.0; broad ICT/SMC skill with 2,008 knowledge cards and optional live market-data tools. Inspect all scripts/data sources and verify methodology before adoption; default to static reference-only subset. |
| `roman-rr/trading-skills` | EXCLUDE from default skill install | Third-party live crypto signals with paid Pro trade levels and external MCP authentication. External signal provider is not independently verified and is not a strategy-evidence source. |
| `Bhala-Srinivash/nse-trading-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | NSE/BSE-specific analysis, risk and position sizing; market-specific rules do not transfer to synthetic indices. Licence not yet verified. |
| `galleonlabs/hypergrok-trading-desk` | REFERENCE_ONLY / SANDBOX_ONLY | MIT Hyperliquid trading desk with multiple roles and execution handoff. Useful approval-flow concepts only; no Hyperliquid connection or live execution. |
| `GMGNAI/gmgn-skills` | NOT VERIFIED | README path returned 404; no installation or capability claims. |
| `zubair-trabzada/ai-trading-claude` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT research-only Claude skills; README states no broker connection or order execution. Verify actual files before copying. |
| `ryanfrigo/kalshi-ai-trading-bot` | REFERENCE_ONLY / SANDBOX_ONLY | MIT, Kalshi-specific prediction-market stack with signed API client, tracking and MCP. Market and settlement semantics do not transfer to Deriv. |
| `Minara-AI/minara-skills` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT and claims Claude/Codex/OpenClaw/Hermes compatibility, but contains multi-asset and on-chain transaction skills. Only static research skills could be considered after inspection. |
| `Jakeschincariol/day-trader-skill` | REFERENCE_ONLY / SKILL_ONLY candidate | MIT Claude skills, research-only, paper-first and no autonomous order placement per README. US equities/news data assumptions; no direct Deriv applicability. |
| `LLMQuant/awesome-trading-agents` | REFERENCE_ONLY | CC0 curated directory, not an installable runtime. Use to discover candidates; review each project independently. |
| `agiprolabs/claude-trading-skills` | NOT VERIFIED | Not yet inspected; no installation. |
| `staskh/trading_skills` | NOT VERIFIED | Not yet inspected; no installation. |
| `KylinMountain/TradingAgents-AShare` | NOT VERIFIED | Not yet inspected; likely market specialization; verify before considering. |
| `himself65/finance-skills` | NOT VERIFIED | Not yet inspected; no installation. |
| `KangOxford/AlphaTrade` | NOT VERIFIED | Not yet inspected; no installation. |
| `tradermonty/claude-trading-skills` | NOT VERIFIED | Not yet inspected; no installation. |
| `Zagitta/gpu-unlock` | EXCLUDE from AURELIA hosts | Linux kernel/boot-time GPU performance override; GPL-2.0. Hardware/boot risk and not an AURELIA trading dependency. |
| `JustAResearcher/gpu-unlock-ada` | EXCLUDE from AURELIA hosts | Linux kernel module and GPU register override for RTX 4090/Ada; boot/driver compatibility risk. |
| `windows-GPU-UNLOCK/Windows-GPU-UNLOCK` | EXCLUDE from AURELIA hosts | Experimental UEFI GPU unlock and Windows handoff. Not an application dependency. |
| `ShyVortex/dlss-unlocked` | EXCLUDE | Game graphics/frame-generation mod. |
| `sudoingX/qwen38-mtp` | REFERENCE_ONLY | Qwen inference optimization notes; not a trading system. Verify model release/benchmark environment before use. |
| `dashdogy/MFG-Unlocker` | EXCLUDE | Windows game frame-generation DLL/mod. |
| `physicsdolphin/nv-uefi-unlocker` | EXCLUDE from AURELIA hosts | GPL-2.0 UEFI/pre-driver GPU register override; significant firmware/boot compatibility risk. |

## Shortlist for deeper review

1. **ML4T skills** — best fit for a research discipline skill subset: leakage, lookahead, CV, cost modelling, and evidence boundary.
2. **backtesting.py** — possible independent baseline comparator only, after realistic execution-cost and intrabar assumptions are verified.
3. **TradingAgents** — research orchestration reference only; keep agents away from broker state and order tools.
4. **Hummingbot / NautilusTrader / OpenAlgo** — architectural reference or isolated adapter-lab candidates, not replacements for AURELIA's canonical capital plane.
5. **OpenMobius-skill** — static reference-only market-structure guidance candidate, subject to methodology, source and script audit.

## Important compatibility findings

- AURELIA currently requires Python >=3.11 and has a deliberately minimal runtime dependency set. Do not add a framework's entire dependency graph to the canonical runtime.
- Several repositories are full trading platforms or autonomous bots. Importing them would duplicate execution, account/session, risk, and ledger responsibilities.
- Strategies built for equities, A-shares, futures, crypto exchanges, Hyperliquid, Kalshi, or Interactive Brokers do not establish edge on Deriv synthetic indices.
- A README win rate or claimed performance is not acceptable qualification evidence. Require source data, point-in-time validity, no lookahead, walk-forward/OOS, instrument-specific costs, slippage, spread, fills, drawdown, expectancy and reproducible artifacts.
- Repository-level review is not complete for every candidate. `NOT VERIFIED` means exactly that, not approved or rejected on code quality.

## Next controlled intake

For each shortlisted candidate: pin a commit; inspect all selected skill/source files, license and dependencies; run isolated tests; add attribution; map the skill to role assignments in `config/agent_tool_skill_assignment.json`; then open a separate PR with explicit no-capital/no-secret regression tests. No bulk installer and no global agent plugin installation.

## Verification status

This PR adds the intake skill and this source triage document only. It does not add third-party dependencies, install a broker connector, register a live agent runtime, change a strategy, change the canonical capital plane, or enable trading. AURELIA live lock remains BLOCKED.
