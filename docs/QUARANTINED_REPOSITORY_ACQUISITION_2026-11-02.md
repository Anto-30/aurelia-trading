# Quarantined Repository Acquisition — 2026-11-02

## Disposition

This document records a preliminary, source-browsed acquisition assessment. It does not certify local cloning, SBOM completeness, vulnerability status, isolated tests, or AURELIA integration. All candidates remain quarantined under `config/external_repo_federation.json`.

Global boundary remains unchanged: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`, `research_capital_authority=false`, and external repositories have no capital authority.

## Repository identity and pinned source heads

| Repository | Observed default-branch HEAD | Pin date | Mode | Initial decision |
|---|---|---|---|---|
| NousResearch/hermes-agent | `fbf6c6c91d8a9ce3008e05c4b51ca60ad05bb85f` | 2026-11-02 | SANDBOX_ONLY | NO-GO for direct AURELIA runtime; sandbox reference only |
| tradermonty/hermes-trading-research-agent-work-package | `9598a9cc21e465438b194e43f35b52d4adf7fe3d` | 2026-11-02 | RESEARCH_ONLY | GO for isolated research/reporting evaluation |
| tradermonty/claude-trading-skills | `121dce2da6760a36a160c73493370fbc26a02ccd` | 2026-11-02 | RESEARCH_ONLY | GO for selected calculation/schema evaluation |
| agiprolabs/claude-trading-skills | `981e1d736cdc02bdc1c55c74ec9224e956414706` | 2026-11-02 | REFERENCE_ONLY | NO-GO for DEX/wallet execution; research snippets only after separate audit |
| Jakeschincariol/day-trader-skill | `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` | 2026-11-02 | REFERENCE_ONLY | NO-GO for broker integration; approval-state-machine reference only |

The originally suggested `tradermonty/hermes` returned GitHub 404. `Julian-dev28/hermes-trader` was not found by the exact owner/repository search. The TradeMonty Hermes profile repository above is not the Hermes Agent runtime; the actual runtime source browsed separately is `NousResearch/hermes-agent`.

## License

The root license files inspected for all five repositories identify MIT. This supports commercial compatibility subject to preserving notices and auditing third-party and vendored components. It is not a dependency-license completeness result. No GPL root license was found; transitive and embedded license obligations remain pending.

## Dependency and SBOM status

- **NousResearch Hermes Agent:** `pyproject.toml` declares Python `>=3.11,<3.15` and exact-pinned direct dependencies for most core packages, with some conditional ranges and an Android VCS pin. A `uv.lock` file exists, but its content was not retrievable through the current file connector. Complete lock and transitive dependency inspection is pending.
- **TradeMonty Hermes profile:** `pyproject.toml` declares PyYAML, with pytest and jsonschema as development extras. The README additionally documents jsonschema and PyYAML installation. No complete lockfile audit performed.
- **TradeMonty Claude skills:** `pyproject.toml` declares jsonschema, packaging, PyYAML, requests, SciPy and yfinance with version ranges; optional/development extras include pytest, Bandit, detect-secrets and pip-audit. No lockfile audit performed.
- **AgiPro skills:** dependencies are documented per skill rather than through a complete root manifest. Inspected execution examples use httpx and solders plus Jupiter/Solana RPC.
- **Day Trader:** README describes core scripts as standard-library Python; broker interaction is via an external Alpaca MCP connector, not direct broker calls from the local ticket script.

CVE status: UNKNOWN - Requires Local Audit. The independent screening service returned no detailed CVE inventory for these repository identifiers; this is not evidence of zero vulnerabilities.

## Security and execution findings

- Hermes Agent is a general agent runtime with terminal backends, tool execution, subagents, messaging, scheduled automation and skill persistence/self-improvement features. It is too privileged for direct use in the AURELIA capital plane. Evaluate only in an isolated, no-secrets sandbox.
- The Hermes trading profile states that it is a research, journaling and risk-review assistant, not an automated trading system. Its profile example uses environment-variable placeholders and an Alpaca paper default. Its README also documents a `curl | bash` installer; do not use that installer in production acquisition.
- TradeMonty Claude skills provide research calculations and schemas, but no native Deriv adapter or Layer 6 integration was established.
- AgiPro's DEX skill documents wallet private-key loading, transaction signing and Solana RPC submission. Its WebSocket examples use WSS endpoints, but the presence of WSS examples does not prove comprehensive payload validation or safe key custody. Do not execute or vendor these pathways.
- Day Trader's broker workflow uses order fingerprints, a risk PASS for the exact order and two human approval gates before an external broker connector. It is US-equity/Alpaca-specific; it does not satisfy Deriv identity, Risk Warden or execution-firewall contracts. Its market-data tools explicitly warn that Yahoo Finance data is unofficial and can lag.

No repository was executed. No live credentials, broker tokens, wallet keys or production secrets were supplied or accessed.

## AURELIA CI and provider findings linked to this review

- PR #247 improves fail-closed behavior when no worker command is configured. Its configured-worker test uses a sleeping Python process; that proves process liveness, not provider authentication. AURELIA's provider-authentication gate remains incomplete.
- PR #248's inspected head `7b9e0bd9ae6ee66f8e474cd803d4e8e06fac09fd` fails the Assurance compile step. Retrieved files end in incomplete declarations/assertions/expressions and the status document is truncated. The CI log separately reports UTF-8 decoding errors. Do not blanket-replace invalid bytes; repair from an attributable source and rerun exact-head CI. Silver Bullet tuning, P1 and P2 remain blocked.
- The current `main` branch does not contain `config/risk_policy.yaml`. The current documented/runtime probability floor remains 0.50–0.75. The proposed 0.55 floor is not active until the canonical policy is reviewed and implemented consistently across runtime, production standard, README, audits and tests.

## Test execution status

No isolated test suite was run in this session. The local container could not resolve GitHub for `git clone`; no Desktop Commander device is connected; and the available Hugging Face job service rejected a minimal Python job request with HTTP 402 Payment Required. Therefore:

- Clone status: NOT COMPLETE.
- Offline tests: NOT RUN.
- CVE/dependency scan: NOT RUN.
- Full secret scan: NOT RUN.
- Full source-tree and network-flow audit: NOT COMPLETE.

Repository-prescribed commands for a future isolated checkout:

```bash
# Hermes trading research profile
make validate
make test
# validate-all additionally requires CLAUDE_TRADING_SKILLS_REPO
make validate-all

# Day Trader
python3 -m unittest discover -s tests -v

# TradeMonty Claude skills
python -m pytest -q
```

For Hermes core and AgiPro, use their exact pinned source checkout and repo-provided test configuration after reading all test and packaging instructions. Do not assume a default pytest invocation is sufficient.

## Promotion criteria

No source is promoted to execution or capital-plane dependencies. Reconsider only after: authenticated and isolated clone; full dependency/license SBOM; offline secret scanning; SAST and CVE scanning against a current advisory database; network-egress and subprocess review; complete offline tests; reproducible build hashes; independent code review; and adapter-level compatibility tests against AURELIA contracts. Any accepted component remains advisory or research-only unless an independent AURELIA release process authorizes otherwise.

## External environment limitations

This PR updates source pins and records evidence only. It does not claim a physical clone or runtime install. AURELIA's agent capability boundary records Dev as NOT_CONNECTED; the current ChatGPT session has GitHub source browsing/writing but no connected desktop shell, Claude Code runtime, DeepSeek harness, or Hermes process. The user can connect an authorized host later to complete offline execution.


## Follow-up intake — 2026-11-02 (23 URLs, 18 unique repositories)

Duplicate URLs were deduplicated: `microsoft/playwright-mcp` (2 occurrences), `QwenLM/qwen-code` (4 occurrences), and `mithun50/openclaw-termux` (2 occurrences). Four repositories were already in the 303-entry registry and had their pins refreshed; fourteen new repositories were added. The registry now contains 317 unique entries.

| Repository | Pinned default-branch HEAD | License metadata | Mode | Disposition |
|---|---|---|---|---|
| earendil-works/pi | `ff2c8931cf8bfa7acb3554258d0b55df79243bb8` | MIT | SANDBOX_ONLY | General agent harness; no built-in filesystem/process/network/credential permission system per README |
| deepseek-ai/dsh-superagent-prototype | `6337fc823ce20251c8de8085948165c81aaa701e` | MIT | SANDBOX_ONLY | Explicitly a research prototype, not production-ready |
| vercel-labs/agent-desktop | `9eb9b296192fcb70bda25e918cd6dd66abfa3d0d` | Apache-2.0 | SANDBOX_ONLY | Desktop UI automation; no connected desktop host; never target broker/admin UIs |
| hackobi/AI-Scalpel-Trading-Bot | `30eed4130d4808a25a5be6a0ee6cf42e3f19bc22` | GPL-3.0 | REFERENCE_ONLY | Freqtrade-derived educational fork; last pushed 2023 |
| microsoft/playwright-mcp | `ec572ee8354015293bed67145db21eed386e876d` | Apache-2.0 | TOOLCHAIN_ONLY | Browser test automation only; no trading credential access |
| freqtrade/freqtrade | `2cebcc38974ac6e606f48dc016e75f9b0b25bc4a` | GPL-3.0 | RESEARCH_ONLY | Active crypto framework; no Deriv synthetic adapter established |
| mithun50/openclaw-termux | `87bc13b4e4bb82b5447d9d0514bd3e38f222fb8b` | MIT | SANDBOX_ONLY | Android/Termux agent gateway; not a qualified persistent trading host |
| cuemacro/finmarketpy | `afeaef28f5c8b78e613e649ecf18a9653dbf41fd` | Apache-2.0 | RESEARCH_ONLY | Backtesting, seasonality, event studies and volatility-targeting reference |
| Alishahryar1/free-claude-code | `653a3444d43c0489c26d1b3a2e2a336b001e20ff` | NOASSERTION | REFERENCE_ONLY | Provider router advertises free-token/API-key fallback; license and installer/secret handling unverified |
| nntaoli-project/goex | `0a7d6619669ffc3164aa8fdceb545a64dc7f2cc4` | MIT | REFERENCE_ONLY | OKX/Binance exchange SDK documents private API keys and order creation; no Deriv support |
| obra/superpowers | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | MIT | TOOLCHAIN_ONLY | Development methodology; corresponding Superpowers skills already installed in this session |
| ruvnet/ruflo | `5f3dacc54b7279e39b172d6027d7989791448e2e` | MIT | SANDBOX_ONLY | High-privilege multi-agent orchestration; README says mods run with account permissions |
| openclaw/openclaw | `744232dfe4ddf40d98ba768efc6a40314eb3b927` | MIT | SANDBOX_ONLY | Host agent gateway with tool execution; security and sandboxing review required |
| letianzj/quanttrader | `224341d57e146aeaa143516049d2f37ff102dbf0` | Apache-2.0 | REFERENCE_ONLY | Last pushed 2024; IB live-trading framework, not Deriv-native |
| ZhuLinsen/daily_stock_analysis | `45381688c34df54470e9166ae69bbca912fdbe8f` | MIT | RESEARCH_ONLY | Multi-market equity/news/LLM research; not a Deriv execution component |
| QwenLM/qwen-code | `14de8a035e5143e4018fda96a641826349546caf` | Apache-2.0 | SANDBOX_ONLY | Existing entry refreshed; daemon defaults to unauthenticated loopback, shared hosts require explicit bearer auth |
| just-nilux/awesome-tradingview | `03d16ff0366351a0eff3945afba212caa410455b` | UNKNOWN | REFERENCE_ONLY | Curated PineScript catalog last pushed 2023; individual scripts need license and repaint/lookahead review |
| agentscope-ai/QwenPaw | `b660bc9a12ae8bf61699c0777b8d11df302a0194` | Apache-2.0 | SANDBOX_ONLY | Personal multi-agent assistant with tools/plugins; sandbox only |

### Follow-up security and integration decision

- **No external source was cloned, installed, executed, or connected to AURELIA in this follow-up.** These are pinned source references, not runtime installations.
- **No repository was granted Deriv credentials, production secrets, host access, broker access, or capital authority.**
- **No new execution adapter is approved.** Freqtrade, GoEx, QuantTrader and AI-Scalpel are not Deriv-native evidence. They cannot be used to place AURELIA trades.
- **No model/provider credentials were sent to free-claude-code, Pi, Ruflo, OpenClaw, Qwen Code, QwenPaw, Hermes or the DeepSeek prototype.** These are untrusted or sandbox-only agent runtimes until separately audited.
- License values above are GitHub repository metadata, not a full license-text or transitive-dependency audit. `NOASSERTION` and `UNKNOWN` are not approvals.
- Full SBOM, CVE/SCA, secret scanning, malware review, network-egress analysis and isolated test suites remain pending. No zero-vulnerability claim is made.

### AURELIA remediation status at follow-up

PR #251's exact head `67adbd21de97823da7aa2e8ac7f5b51010adc66c` has passing GitHub Assurance, Agent Federation Audit and Agent Continuity Watchdog workflows. Its Assurance run still reports `DERIV_AUTH_MODE=INVALID`, `DERIV_AUTH_PREREQUISITES=NOT_READY`, and skips authenticated Deriv session, broker evidence and verify-only lifecycle steps. The same run reports the PAT-only App ID requirement as false because the mode is invalid; this does **not** prove an App ID is configured. No live-trading gate was opened.

The separate `configure-deriv-auth-mode.yml` workflow is manual and protected by the `production` GitHub environment. It requires an operator to choose `pat` or `oauth`; the correct choice cannot be inferred from token presence. It has not been dispatched. Do not merge or run it until the correct mode is confirmed from the credential's provenance and provider setup. If PAT is selected, configure `DERIV_APP_ID` as a protected GitHub environment secret; never source tokens from plaintext Drive/Library files or commit them.


### Registry integrity correction

The new registry test detected a pre-existing malformed 41-character commit pin for `Anil-matcha/open-dots`. GitHub returned a permanent repository redirect to repository ID `645381450`, but the public repository connector could not resolve a canonical owner/name or current commit. The entry is now `REFERENCE_ONLY`, its invalid SHA was removed, and `pin_validation_status=UNRESOLVED_REPOSITORY_REDIRECT`. It is not treated as a pinned or approved source. This prevents an invalid identifier from being mistaken for a reproducible source pin.
