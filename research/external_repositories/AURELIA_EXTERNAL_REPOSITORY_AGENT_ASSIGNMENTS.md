# External Repository Sync — Agent Assignments

The requested repositories are synchronized into AURELIA as pinned external intelligence sources. Assignment is intentionally separated from capital execution.

| Repository | AURELIA owner | Allowed use | Capital authority |
|---|---|---|---|
| ajaxorg/ace | Command Center UI / Engineering | Browser editor and code-inspection UI research | None |
| remorses/playwriter | Operations QA / Browser Automation | Non-production browser validation and evidence capture | None |
| openinterpreter/openinterpreter | Engineering / Research Orchestrator | Sandboxed coding-agent experiments and maintenance research | None |
| morluto/rea | Security / Reverse Engineering | Static/runtime reverse-engineering investigations | None |
| hackingthemarkets/tradingview-binance-strategy-alert-webhook | Strategy Research | Webhook architecture and alert-pattern research | None |
| jamesmawm/High-Frequency-Trading-Model-with-IB | Quant Research / Microstructure | Historical HFT, pairs and mean-reversion research | None |
| blampe/IbPy | Legacy Broker Research | Compatibility/history reference only | None |
| nntaoli-project/goex | Crypto Broker Research | Exchange abstraction comparison only | None |

## Admission rule

A repository is not a production dependency merely because it is pinned here. Runtime adoption requires a bounded adapter, source pin, dependency/license/security review, tests, provenance, and compatibility with the existing AURELIA release gates.

## Explicit exclusions

- No external repository may write to `config/LIVE_LOCK.yaml`.
- No external repository may set `FINAL_EXECUTION_AUTHORIZATION`.
- No external repository may read or print production secrets.
- No Binance, OKX, or Interactive Brokers execution path is imported into the Deriv capital plane.
- Archived/obsolete broker libraries remain quarantined.
- Browser/coding agents remain sandbox-only.

This preserves the existing AURELIA architecture rather than creating a second trading engine.


## LLM gateway and agent infrastructure sources added 2026-10-09

| Repository | Assigned agents | Allowed use | Capital authority |
|---|---|---|---|
| BerriAI/litellm | GoogleAgentSkills, ClaudeCode, GrokBot, JEV, AURELIA | Sandbox gateway architecture, provider routing, guardrails and observability review; security review required | None |
| LiteLLM-Labs/litellm-agent-control-plane | GrokBot, ClaudeCode, GoogleAgentSkills, JEV, AURELIA | Agent routing/control-plane architecture review only | None |
| BerriAI/litellm-docs | GLM, ClaudeCode, JEV, AURELIA | Documentation and security-advisory reference | None |
| BerriAI/liteLLM-proxy | ClaudeCode, GrokBot, JEV | Legacy proxy reference only | None |
| numman-ali/cc-mirror | ClaudeCode, GrokBot, JEV | Isolated developer tooling research; no production provider credentials | None |
| BerriAI/litellm-pgvector | ClaudeCode, GoogleAgentSkills, JEV | Sandbox vector-memory integration reference | None |
| LiteLLM-Labs/litellm-rust | ClaudeCode, GoogleAgentSkills, GrokBot, JEV | Gateway prototype research | None |
| langchain-ai/langchain-litellm | ClaudeCode, GoogleAgentSkills, GrokBot, JEV | LangChain adapter compatibility/security research | None |

The user requested these sources be synced across AURELIA, ChatGPT, Claude and development tooling. This PR records and routes the source pins through AURELIA's existing federation manifests for Claude Code, Grok/JEV, GoogleAgentSkills and the AURELIA supervisor. It does **not** claim physical installation into an unconnected Claude Code host, a separate Dev runtime, or persistent ChatGPT workspace. ChatGPT can consult these public references in-session; persistent external-runtime installation requires the corresponding host integration.



## Freebuff / Codebuff source assignments — 2026-10-09

| Repository | Assigned agents (primary first) | Allowed use | Capital authority |
|---|---|---|---|
| `jxjhheric/freebuff2api-wokers` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference-only review. Do not deploy or invoke its Freebuff upstream routes. | None |
| `kele68108/Freebuff2API-Optimized` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Fork uses multi-account token rotation and session-reuse optimizations; documentation/reference review only. | None |
| `t479842598/freebuff2api-vercel` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference only. No deployment, token import, fingerprint adaptation, or production credentials. | None |
| `HengXin666/freebuff-proxy` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — README describes a reverse-engineered upstream protocol and multi-account pool; no runtime use. | None |
| `lza6/Freebuff-2API` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference-only. It supports token/cookie import and account pooling; never provide AURELIA or Deriv credentials. | None |
| `NetroIndonesia/freebuff2api` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Upstream README explicitly warns of Terms-of-Service risk and possible account restrictions. Do not deploy or use for restriction evasion. | None |
| `XxxXTeam/freebuff2api` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference only. No token collection via untrusted external pages and no production deployment. | None |
| `Quorinex/Freebuff2API` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — README describes randomized request fingerprints and multi-token rotation; reference-only, no evasion or deployment. | None |
| `pingmike2/freebuff2api-wokers` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference only. README says Cloudflare Worker deployment can increase account-ban risk. | None |
| `CodebuffAI/freebuff` | ClaudeCode, GoogleAgentSkills, JEV | REFERENCE_ONLY — Official upstream client reference only; not a substitute for provider-supported access or AURELIA authorization. | None |
| `VenTheZone/freebuff-gate` | PlaywrightCLI, ClaudeCode, GoogleAgentSkills, JEV | SANDBOX_ONLY — Sandbox only; not installed into the AURELIA Command Center and not exposed on public interfaces. | None |
| `Praket7/freebuff-mcp` | GoogleAgentSkills, ClaudeCode, PlaywrightCLI, JEV | SANDBOX_ONLY — High-trust local bridge: can send requests to Freebuff and read ordinary project files. Isolated sandbox and manual approvals only; redaction is not a security boundary. | None |
| `Jakevin/codex-freebuff-web` | ClaudeCode, GoogleAgentSkills, JEV | SANDBOX_ONLY — Sandbox-only adapter for developer use; no production account data or AURELIA/Deriv secrets. | None |
| `TheMetalStorm/herdr-freebuff-plugin` | GrokBot, ClaudeCode, JEV | REFERENCE_ONLY — Plugin scrapes terminal content to infer agent state; reference-only until privacy and least-privilege review. | None |
| `Heartcoolman/FreeBuff` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Local compatible bridge only as architecture reference; do not route production credentials through it. | None |
| `HaizhuAI/Freebuff2apic` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference only; repository description identifies account-pool management and proxy routing. | None |
| `0xgetz/freebuff-9router` | GoogleAgentSkills, ClaudeCode, GrokBot, JEV | REFERENCE_ONLY — Reference-only adapter/gateway integration; no production credentials or live account-pool deployment. | None |
| `aminkalantari842-ui/global-intelligence-os` | GrokBot, ClaudeCode, GoogleAgentSkills, JEV | REFERENCE_ONLY — Repository has no declared license in API metadata and a broad project description; inspect before any use. | None |
| `6yte96/freebuffet` | ClaudeCode, GoogleAgentSkills, GrokBot, JEV | SANDBOX_ONLY — Sandbox-only CLI review. It can generate provider configuration; never write secrets or config into production hosts automatically. | None |

All 19 entries are pinned references or isolated development candidates; none is being installed into production. Use official upstream APIs and respect provider terms, session policies, quotas, and account restrictions. No AURELIA, Deriv, GitHub or production-host credentials may flow through these sources. Physical integration into ChatGPT, Claude Code or a distinct Dev runtime is not claimed; the repo manifests and agent instructions are the persisted routing artifact for this change.
