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
| BerriAI/litellm | ClaudeCode, GoogleAgentSkills, GrokBot, JEV, AURELIA | Sandbox gateway architecture, provider routing, guardrails and observability review; security review required | None |
| LiteLLM-Labs/litellm-agent-control-plane | ClaudeCode, GoogleAgentSkills, GrokBot, JEV, AURELIA | Agent routing/control-plane architecture review only | None |
| BerriAI/litellm-docs | ClaudeCode, GoogleAgentSkills, JEV, AURELIA | Documentation and security-advisory reference | None |
| BerriAI/liteLLM-proxy | ClaudeCode, GrokBot, JEV | Legacy proxy reference only | None |
| numman-ali/cc-mirror | ClaudeCode, GrokBot, JEV | Isolated developer tooling research; no production provider credentials | None |
| BerriAI/litellm-pgvector | ClaudeCode, GoogleAgentSkills, JEV, AURELIA | Sandbox vector-memory integration reference | None |
| LiteLLM-Labs/litellm-rust | ClaudeCode, GoogleAgentSkills, GrokBot, JEV | Gateway prototype research | None |
| langchain-ai/langchain-litellm | ClaudeCode, GoogleAgentSkills, GrokBot, JEV, AURELIA | LangChain adapter compatibility/security research | None |

The user requested these sources be synced across AURELIA, ChatGPT, Claude and development tooling. This PR records and routes the source pins through AURELIA's existing federation manifests for Claude Code, Grok/JEV, GoogleAgentSkills and the AURELIA supervisor. It does **not** claim physical installation into an unconnected Claude Code host, a separate Dev runtime, or persistent ChatGPT workspace. ChatGPT can consult these public references in-session; persistent external-runtime installation requires the corresponding host integration.

