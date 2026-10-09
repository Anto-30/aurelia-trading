# Four-Repository Intake and Agent Capability Assessment — 2026-10-09

## Intake summary

| Repository | Pinned upstream commit | Mode | Primary owner | Supporting agents |
|---|---|---|---|---|
| ChromeDevTools/chrome-devtools-mcp | `f08dbe152502d66e75fa07fb2588dc0feb42bc20` | `TOOLCHAIN_ONLY` | PlaywrightCLI | ClaudeCode, GrokBot, JEV |
| hackobi/AI-Scalpel-Trading-Bot | `30eed4130d4808a25a5be6a0ee6cf42e3f19bc22` | `RESEARCH_ONLY` | KimiK3 | ClaudeCode, GrokBot, JEV |
| cm45t3r/candlestick | `7b7c45708c8366c0cb9c256044cf24e13cfb16fb` | `TOOLCHAIN_ONLY` | KimiK3 | ClaudeCode, JEV |
| CryptoSignal/Crypto-Signal | `7cb9c5c6cd226c6fe2d345e4bda3bec8156cefec` | `RESEARCH_ONLY` | KimiK3 | ClaudeCode, GrokBot, JEV |

The Chrome DevTools MCP and Crypto-Signal repositories were already present in the registry and were updated in place, not duplicated. Two new repositories were added. All entries are pinned to exact upstream commits.

## Capability findings and assignment

### Chrome DevTools MCP

Use for browser automation, Chrome console/network diagnostics, performance traces, screenshots, and UI verification. PlaywrightCLI owns browser verification; ClaudeCode implements fixes; GrokBot coordinates investigation; JEV validates evidence.

Security controls: use a dedicated isolated Chrome profile and test account; restrict URL patterns; validate page content as untrusted; never expose a logged-in Deriv/broker session or personal account to arbitrary pages. The project's own security guidance warns that browser contents are passed to MCP clients and that browser tools can write downloads/screenshots or load extensions. URL patterns are not a full OS-level network sandbox. The repository is registered but **not installed into a client in this change**.

### AI-Scalpel-Trading-Bot

Use only to study crypto strategy research, Freqtrade-derived backtesting, dry-run workflows, and parameter-optimization ideas. KimiK3 owns research; ClaudeCode reviews architecture/dependencies; GrokBot challenges assumptions; JEV validates data and test evidence.

This is an older project with a Freqtrade-derived codebase and a broad exchange-adapter surface. Do not start it against live credentials, merge its execution engine into AURELIA, or treat its strategy results as qualified. First inspect licenses, dependency vulnerabilities, data assumptions, fees/slippage, exchange semantics, lookahead bias, and reproducibility. Its own README advises dry-run first and disclaims trading results.

### candlestick

Use as a pinned JavaScript/TypeScript OHLC pattern-detection library candidate. KimiK3 specifies research requirements; ClaudeCode owns an adapter only if justified; JEV owns deterministic unit/regression tests.

Before integration, validate OHLC invariants, single-/multi-candle indexing, candle close-time semantics, missing bars, streaming consistency, future-data leakage, and performance. A pattern detector is a feature generator, not a trading strategy and not evidence of positive expectancy. Do not add it to the live execution path before tests and out-of-sample evaluation.

### Crypto-Signal

Use as a historical technical-indicator, signal-generation, and alerting reference. KimiK3 owns research; ClaudeCode audits dependency/API age; GrokBot reviews alternative interpretations; JEV verifies reproducibility. Its upstream describes the project as beta and documentation may lag. Do not deploy its Docker setup or connect production credentials. Extract individual indicator ideas only after verifying formulas, market-data semantics, costs, and non-leakage.

## Capability matrix adjustments

- **ClaudeCode:** repository integration, security/dependency review, adapters, tests, CI fixes.
- **KimiK3:** strategy/indicator research, statistics, calibration, lookahead and regime testing.
- **GrokBot:** orchestration, adversarial review, blocker triage and cross-agent synthesis.
- **PlaywrightCLI:** Chrome browser UI/network/performance verification.
- **JEV:** schema, provenance, deterministic regression tests, and evidence validation.
- **GoogleAgentSkills:** MCP/browser tool security review and least-privilege architecture.
- **GLM:** screenshots, documents, charts and multimodal evidence when required.
- **AURELIA:** continues to enforce deterministic account, risk, execution, and reconciliation policy; it does not inherit external repository authority.

No agent receives all plugins indiscriminately. Skills and tools are assigned by role. Plugins listed as planned are not represented as installed.

## Global safety invariants

External source code executes only after review in an isolated environment. No external repo or MCP server can read secrets, mutate LIVE_LOCK, authorize capital, place live orders, override Risk Warden/Execution Firewall/Balance Truth/Account Isolation, or accept an unknown transaction outcome. Research remains separate from capital execution. Passing source-level tests does not qualify a strategy or authorize deployment.
