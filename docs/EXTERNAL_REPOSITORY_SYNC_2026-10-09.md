# External repository federation sync — 2026-10-09

## Scope

Historical baseline: 154 public repositories were registered in an earlier sync. The 2026-10-09 follow-on sync now adds eight LiteLLM/agent-infrastructure sources, bringing the external repository federation from 189 to 197 unique pinned repositories and the agent-skill source registry from 88 to 96 sources. This is registry/source synchronization, not a claim that all source code was physically installed or admitted into the runtime. It does not copy upstream source into the capital plane or claim that external agent runtimes have been physically installed.

## Pinned sources and routing

| Repository | Pinned commit | Mode | Primary agent | Intended use |
|---|---|---|---|---|
| CryptoSignal/Crypto-Signal | 7cb9c5c6cd226c6fe2d345e4bda3bec8156cefec | RESEARCH_ONLY | KimiK3 | Legacy crypto technical-analysis research reference; last commit checked 2022-08-09 |
| Kappaemme-git/codex-first-customer-finder-skill | d3f6964bd989745ac183edbd545c588a68451146 | SANDBOX_ONLY | ClaudeCode | Evidence-backed customer discovery, outside trading execution |
| Neeeophytee/finding-unknowns-skills | ca5696a0f08d2de6b2997fff1d6cc05c3ed587cc | SANDBOX_ONLY | ClaudeCode | Unknowns, assumptions, requirements and regression evidence |
| he-yufeng/FindJobs-Agent | 591fe6b451db98fe0bebb8f92a7b9902b0fd6079 | SANDBOX_ONLY | ClaudeCode | Job/skill analysis only; not a trading component |
| davepoon/buildwithclaude | 616deb5c66db0b06a6afeb7ae675e70a1b6e3b34 | SANDBOX_ONLY | ClaudeCode | Discovery catalogue; individual plugins must be reviewed before install |
| workersio/skills | 0e3950fc7b284db4f6b317e48bcb99edd2c1e3bb | SANDBOX_ONLY | ClaudeCode | Bug triage, debugging and regression testing |

Supporting assignments include GrokBot, JEV and AURELIA. Quantitative crypto research also includes KimiK3. The user's “Dev” label is not a canonical agent ID in the checked registry; this batch routes engineering work to ClaudeCode rather than inventing a second runtime identity.

## Inventory validation

- 154/154 registered repository URLs were reachable in the main-branch sync check.
- 154/154 repository records now have a pinned default-branch commit SHA; the federation validator rejects duplicate repository names or any remaining `SYNC_REQUIRED` entries.
- A pin records a source revision; it does not mean that code has been installed, reviewed for production use, or qualified as a strategy.

## Guardrails

- All source SHAs are pinned; external code execution remains deny-by-default.
- Every new skill source has `capital_authority: false`.
- Community sources cannot read or log production secrets, mutate `LIVE_LOCK`, authorize trades, or submit broker transactions.
- The legacy Crypto-Signal project is research reference only and is not treated as a qualified Deriv strategy.
- `LIVE_LOCK.yaml` remains unchanged and live execution remains blocked.
- This is a repository registry sync. Physical installation into Claude Code, a distinct Dev runtime, Grok, or the production host is **not claimed** without a connected host and runtime verification.

## Related engineering fixes in this PR

- Scheduled Deriv verification now selects the protected `production` environment and accepts the supported token/account-binding aliases.
- Prospective R100 collection preserves partial state after a feed/API exception and retries once in the workflow; a failed run remains failed and cannot authorize trading.
- Federation audit validates that the six sources remain pinned, assigned to known canonical agents, and non-authoritative.


## Follow-on LiteLLM and agent gateway sync — 2026-10-09

Eight source pins were added: `BerriAI/litellm`, `LiteLLM-Labs/litellm-agent-control-plane`, `BerriAI/litellm-docs`, `BerriAI/liteLLM-proxy`, `numman-ali/cc-mirror`, `BerriAI/litellm-pgvector`, `LiteLLM-Labs/litellm-rust`, and `langchain-ai/langchain-litellm`. Exact commit SHAs, assignments, modes, and restrictions are maintained in `config/external_repo_federation.json` and `config/agent_skill_federation.json`.

**Security finding:** upstream LiteLLM security advisories include recent critical/high issues, and the official March 2026 security notice documented compromised PyPI versions 1.82.7 and 1.82.8. Therefore the sync registers these projects as references/sandbox-only; it does not run `pip install litellm`, add them to production dependencies, or give them access to secrets. Any later adoption must pin a reviewed release, verify release signatures where supported, scan transitive dependencies, and pass isolated tests.

**Scope limitation:** the registry can be synchronized into the existing AURELIA repository and made available as source context to the connected agent workflows. No connected Claude Code host, separate Dev runtime, or persistent ChatGPT workspace was available to physically install software into during this task. No such installation is claimed.



## Supplemental source batch — Freebuff / provider-gateway review, 2026-10-09

The original inventory counts recorded above are a historical snapshot. The subsequent LiteLLM and Freebuff registrations bring the current main-branch manifests to **216 external repository entries** and **115 skill/source entries** once the open federation PR is merged. The 19 Freebuff-related source pins are documented in `docs/AURELIA_FREEBUFF_REPOSITORY_REVIEW_2026-10-09.md`. They remain reference/sandbox sources, not production installs. External code execution remains deny-by-default, and no source has capital authority.


## Pine Script / TradingView / Pinecone batch — 2026-10-09

Twenty additional repositories were pinned on branch `integration/pinescript-toolchain-federation-20261009`. After merge, the expected inventory is 236 external repositories and 135 skill/source records. Review decisions and exact pins are documented in `docs/AURELIA_PINESCRIPT_TRADINGVIEW_REPOSITORY_REVIEW_2026-10-09.md`. These are source registrations, not claims of installation or live readiness.
