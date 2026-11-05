# TradingAgents research federation for AURELIA

**Status:** pinned research references; no external package installed or imported into the AURELIA runtime.  
**Reviewed:** 2026-11-05.  
**Execution mode:** `RESEARCH_ONLY`.  
**Canonical implementation owner:** ClaudeCode (when a verified ClaudeCode worker runtime is connected).  
**Research/adversarial support:** KimiK3, GrokBot and JEV (only when their runtimes are independently verified).

## Decision

Integrate the useful research workflow patterns from the four repositories through AURELIA's existing worker JSONL contract. Do not install four complete applications, add their dependency trees to AURELIA's Python environment, or create a second capital/portfolio/execution manager.

The original TauricResearch project is the primary architecture reference. The A-share forks are market-specialization references, not valid sources of synthetic-index or Deriv assumptions. The forks overlap substantially; they are not four independent alpha engines and should not be counted as four independent confirmations.

## Pinned source set

Pins are full commit SHAs resolved from each repository's default-branch HEAD on 2026-11-05. Re-pin only through a reviewed change with a source diff and license review.

| Source | Commit | License finding | Permitted AURELIA use |
|---|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | `9fa1196fffbcfd9de5146d2dd2869df84ab99838` | Apache-2.0 | Primary architecture and research workflow reference; reuse subject to Apache notices and attribution |
| [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | `51060a7682cf51810b4bc3a704829438d18cd8dc` | Hybrid: Apache-2.0 for specifically listed directories; proprietary source-available restrictions for `app/`, `frontend/`, `core/` | Inspect only paths explicitly covered by Apache-2.0. No copying restricted application/core components into commercial AURELIA without a commercial licence |
| [simonlin1212/TradingAgents-astock](https://github.com/simonlin1212/TradingAgents-astock) | `3a9171182304e87042743dde245c64922e04ed96` | Apache-2.0 | A-share analyst-role, data-source and market-rule research reference; preserve notices and attribution if code is reused |
| [KylinMountain/TradingAgents-AShare](https://github.com/KylinMountain/TradingAgents-AShare) | `63b25eda444377366ab6e4e265228454c51713f3` | Mixed: Apache-2.0 upstream portions; PolyForm Noncommercial 1.0 for new API/frontend and significant modifications | Architecture and feature reference only. No copying restricted additions/modifications into commercial AURELIA without explicit commercial permission |

The authoritative machine-readable pins and restrictions are in `config/external_repo_federation.json`.

## What to adopt

1. **Analyst decomposition:** independent market-structure, technical, news/sentiment and fundamental/context reports where the instrument and data actually support those dimensions.
2. **Bull/bear challenge:** a structured debate that requires each side to cite source timestamps, data identifiers, assumptions and falsifiable counterarguments.
3. **Research synthesis:** ClaudeCode coordinates implementation and structured synthesis; KimiK3 owns quantitative/statistical challenge; GrokBot challenges orchestration and external assumptions; JEV validates schemas, evidence lineage and deterministic acceptance. Each role is advisory.
4. **A-share-only research:** the Policy, Hot Money and Lock-up Expiry analyst concepts are relevant only to Chinese equities. They must not be applied to Deriv synthetic indices.
5. **Decision journal/backtest ideas:** inspect point-in-time data handling, delayed settlement and run isolation as design references. A report, model rating or paper-trading result is not strategy qualification.

## AURELIA integration boundary

- **Entry:** Layer 9 research orchestration submits a bounded task to `PersistentAgentFederation`.
- **Transport:** the existing `aurelia.agent-task.v1` JSONL worker contract. Do not create a second bus, claim API or model-specific capital pathway.
- **Output:** schema-validated, content-addressed research artifact under the configured evidence root. Include source commit, run ID, instrument, venue, timeframe, data-vintage/as-of time, source IDs, model/provider identifier, prompt/config hash, assumptions, conflicts, confidence calibration and explicit limitations.
- **Review:** independent validation must distinguish worker-submitted artifacts from verified findings. Worker self-attestation, consensus among correlated forks, file existence and LLM confidence are not proof.
- **Downstream:** findings may be considered by Layer 9 research and the canonical strategy qualification pipeline. They cannot directly mutate the strategy registry, capital plane, risk limits, order intent or broker adapter.
- **Risk and execution:** Layer 6 remains the deterministic risk authority. The execution firewall and release authority remain canonical and independent. External portfolio managers, traders and simulated exchanges are not wired to Deriv.

### Required task envelope

Use the existing JSONL protocol and one assigned worker per task. A research task should carry only non-secret data and references:

- `task_type=TRADINGAGENTS_RESEARCH`
- `source_repository` and pinned `source_commit`
- `instrument_id`, venue, timeframe and requested research horizon
- approved data references and as-of timestamp
- research questions, permitted analyst roles and output schema
- explicit `capital_authority=false` and no execution permission fields

The worker must return a relative evidence reference and bounded result metadata. AURELIA snapshots the evidence bytes. A separate verifier checks content, reproducibility, source freshness and point-in-time integrity.

## Claude and the existing agent federation

ClaudeCode is assigned as the integration owner in the external repository registry. KimiK3, GrokBot and JEV are supporting roles. This is routing configuration, not proof that Claude, Kimi, Grok or JEV provider runtimes are connected.

A local worker must pass the current JSONL handshake and task-claim protocol. The handshake proves protocol compatibility only; provider identity and authentication require a separate, provider-specific verified session. Until that exists, the worker remains unavailable and tasks remain pending. Do not treat a configured command, skill file, model name or agent roster entry as a running agent.

ClaudeCode's repository instructions should use this document when reviewing TradingAgents-derived work. Do not place API keys in prompts, task payloads, command-line arguments or evidence artifacts. Do not reuse a user's Claude subscription session through unofficial relays or credential bridges.

## Dependency and environment decision

No TradingAgents dependency is added to `pyproject.toml` or `requirements.txt`.

Reasons:
- AURELIA's runtime is Python `>=3.11` with a deliberately small dependency surface.
- The upstream framework is a separate LangGraph research application with a substantial dependency graph and its own cache, checkpoint and memory state.
- The A-share forks add market-specific data vendors and application services (for example AKShare/BaoStock, MongoDB/Redis, web APIs and frontends) that AURELIA does not need for Deriv synthetic research.
- Mixing these dependencies into the canonical broker/runtime environment increases supply-chain, resolver, runtime and credential-isolation risk.

If a future adapter needs the upstream package, run it in a separately locked and isolated research environment/container, pin the exact commit and dependency lock, use no broker credentials, restrict filesystem/network access, and communicate only through the existing JSONL protocol. No external source checkout is executed by AURELIA's production runtime.

## Qualification gates

Before any TradingAgents-derived research can influence a strategy decision:
1. Confirm instrument/data-source compatibility; reject A-share-only assumptions for synthetic indices.
2. Enforce point-in-time data: no future filings, news, bars or revised values in historical decisions.
3. Seal train/validation/OOS windows before tuning; prevent overlapping labels and leakage.
4. Record provider/model version, prompt/config hash, stochastic settings and retries.
5. Measure calibration, Brier/log loss where applicable, coverage, disagreement and stability; do not use raw LLM confidence as calibrated probability.
6. Benchmark against simple deterministic baselines and ablations; test whether agent debate adds measurable incremental value after costs.
7. Apply spread, payout, commission, slippage and execution-latency costs from verified instrument-specific sources.
8. Run walk-forward/OOS, prospective paper testing and persistent soak under the existing AURELIA qualification framework.
9. Require independent review and all canonical registry evidence before promotion.

No result in these four repositories qualifies an AURELIA strategy. The framework's own research disclaimer also makes clear that output depends on models, data, periods and configuration.

## Explicit non-goals

- No live or demo broker order submission.
- No external portfolio manager or simulated exchange connected to the AURELIA executor.
- No automatic strategy registration or promotion.
- No changes to `config/LIVE_LOCK.yaml`, capital authority, risk thresholds or release gates.
- No unrestricted shell, filesystem, network, browser or production-secret access for worker processes.
- No claim that Claude/DeepSeek/Hermes/Kimi/Grok/JEV/Dev are connected until authenticated runtime evidence exists.

## Source links

- [TauricResearch README](https://github.com/TauricResearch/TradingAgents)
- [TradingAgents-CN README](https://github.com/hsliuping/TradingAgents-CN)
- [TradingAgents-Astock README](https://github.com/simonlin1212/TradingAgents-astock)
- [TradingAgents-AShare README and licence](https://github.com/KylinMountain/TradingAgents-AShare)
- [AURELIA worker protocol](../agents/WORKER_TASK_PROTOCOL.md)
- [AURELIA external repository registry](../../research/external_repositories/AURELIA_EXTERNAL_REPOSITORY_REGISTRY.md)
