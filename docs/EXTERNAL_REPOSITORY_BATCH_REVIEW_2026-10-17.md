# External Repository Batch Review — 2026-10-17
**Scope:** 69 submitted URLs, 67 unique repositories (two repeated URLs: `RightNow-AI/openfang` and `6551Team/opennews-mcp`). All 67 unique repositories are present in the AURELIA external-source registry. This is an intake triage and selected-source review, not a full security certification.

## Executive decision

- **No repository is approved for direct integration into AURELIA's capital/execution plane.**
- Trading engines, broker adapters, and MCP tools capable of live order placement remain **RESEARCH_ONLY or SANDBOX_ONLY**. Research-only means source/reference use, not safe to install or execute.
- SDKs/specifications may be considered as **TOOLCHAIN_ONLY** after dependency, license, provenance, and version review.
- Broad agents, memory services, connector gateways, desktop shells, OSINT/reverse-engineering tools, and messaging gateways remain sandboxed; never give them production secrets or unrestricted network/filesystem access.
- Public repository metadata and selected README/source files were inspected through GitHub APIs. Repositories were **not cloned or executed in an isolated runner** for this batch. No complete dependency/SBOM/secret/malware scan, reproducible build, full test suite, performance benchmark, or deployment validation is claimed.
- A pinned SHA records the inspected source revision only; it does not prove the source was fully reviewed or that a CI run tested that exact SHA.

## Portfolio inventory

The following rows record repository, reported license metadata, pinned revision and registry mode. License labels are GitHub metadata or repository declarations, not legal clearance for transitive dependencies, models, weights, assets or all subdirectories.

| Repository | License metadata | Pinned revision | Registry mode |
|---|---|---|---|
| [`evolution-foundation/evolution-api`](https://github.com/evolution-foundation/evolution-api) | NOASSERTION | `fa09d37892cdbb1d65a250155d293d92230c5b30` | SANDBOX_ONLY |
| [`PublicAffairs/openai-gemini`](https://github.com/PublicAffairs/openai-gemini) | MIT | `61a83bd9d0def59811624b6ae7d8213a231185d0` | SANDBOX_ONLY |
| [`openai/openai-python`](https://github.com/openai/openai-python) | Apache-2.0 | `bfada5040b0171cd0ae61aefae8c78fcf83c804a` | TOOLCHAIN_ONLY |
| [`nirholas/modelcontextprotocol.name`](https://github.com/nirholas/modelcontextprotocol.name) | NOASSERTION (root all rights reserved; nested x402 facilitator separately MIT) | `f945ce4d75c6de834071c18e11e0a38a44f5862b` | SANDBOX_ONLY |
| [`navaneeshnagarajan/FlintTrade`](https://github.com/navaneeshnagarajan/FlintTrade) | AGPL-3.0 | `a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d` | RESEARCH_ONLY |
| [`euriska/opentrader`](https://github.com/euriska/opentrader) | Apache-2.0 | `d430a4448ebd7002e77d3996e678cf752edecfdd` | RESEARCH_ONLY |
| [`QBT-Labs/openmm-mcp`](https://github.com/QBT-Labs/openmm-mcp) | MIT | `7f1036837d3100625f750e6bd7801534641c2295` | SANDBOX_ONLY |
| [`Synter-Media-AI/mcp-server`](https://github.com/Synter-Media-AI/mcp-server) | MIT | `000d446f465687a5a1249a268e9bfa3f6a3e597d` | SANDBOX_ONLY |
| [`Blave-TW/blave-agent`](https://github.com/Blave-TW/blave-agent) | Apache-2.0 | `effbc4bffbece9da445bdc70bbff590f8c91cf38` | RESEARCH_ONLY |
| [`kerryjiang/OpenEtradeMcp`](https://github.com/kerryjiang/OpenEtradeMcp) | Apache-2.0 | `a53a007c1dba329e79669adbc58a3552a2f4f74e` | SANDBOX_ONLY |
| [`YoungCan-Wang/WyckoffTradingAgent`](https://github.com/YoungCan-Wang/WyckoffTradingAgent) | AGPL-3.0 | `9e848396975062ba22eb76185405728c85a50022` | RESEARCH_ONLY |
| [`pineforge-4pass/pineforge-engine`](https://github.com/pineforge-4pass/pineforge-engine) | Apache-2.0 | `3fc010a8bb6cb460302c9ac6c34e7bba2e548f89` | RESEARCH_ONLY |
| [`LuxAlgo/edge-stats`](https://github.com/LuxAlgo/edge-stats) | MIT | `a48259887962d0f67a27d2b0815e2df9a52efca5` | RESEARCH_ONLY |
| [`mirror29/openfinclaw-cli`](https://github.com/mirror29/openfinclaw-cli) | NOASSERTION | `f48e8117eb0364a60b4f780361063befc97e5b33` | SANDBOX_ONLY |
| [`masdevid/mt5-quant`](https://github.com/masdevid/mt5-quant) | MIT | `2a6cd8015a246032a286864d131309a0094c2d17` | SANDBOX_ONLY |
| [`YichengYang-Ethan/oracle3-prediction-market-agent`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent) | Apache-2.0 | `267fb7c48dae7c4ff8922c02a3a223443e51bf0b` | RESEARCH_ONLY |
| [`Bitget-AI/agent_hub`](https://github.com/Bitget-AI/agent_hub) | MIT | `2551419578abff99baad19b018cab1a963c62306` | SANDBOX_ONLY |
| [`Superior-Trade/superior-skills`](https://github.com/Superior-Trade/superior-skills) | MIT | `9d41db54b231f77e35610a73230eaeffcb456215` | SANDBOX_ONLY |
| [`G-OTW/OpenTraderWorld`](https://github.com/G-OTW/OpenTraderWorld) | NOASSERTION (source-available claims require legal review) | `8df74511c2d1c86909188363c302b83814915793` | RESEARCH_ONLY |
| [`TokenRhythm/opensquilla`](https://github.com/TokenRhythm/opensquilla) | Apache-2.0 | `d3f926c17e361b27f0410e6ea52526c9a2bcbb3d` | SANDBOX_ONLY |
| [`mogons/noraz-agent`](https://github.com/mogons/noraz-agent) | MIT | `8f53497b2b47641de67692606053d4c5343bcfa6` | SANDBOX_ONLY |
| [`Open-Agent-Tools/open-stocks-mcp`](https://github.com/Open-Agent-Tools/open-stocks-mcp) | Apache-2.0 | `b50f61e275a412dd71ec5642cccca9206462724a` | SANDBOX_ONLY |
| [`maghdam/chatgpt-trading-strategy-assistant`](https://github.com/maghdam/chatgpt-trading-strategy-assistant) | MIT | `809c30e92bb1b8e835a0c45ca673c80379b0b9a5` | SANDBOX_ONLY |
| [`6551Team/opennews-mcp`](https://github.com/6551Team/opennews-mcp) | MIT | `e329f36187e4a51a0878823e4fdd4d8f42134e80` | RESEARCH_ONLY |
| [`aaif-goose/goose`](https://github.com/aaif-goose/goose) | Apache-2.0 | `bfcc6ee6f1ee18d0c4c852a65c49b25f87ee40dc` | SANDBOX_ONLY |
| [`BlockRunAI/awesome-OpenClaw-Money-Maker`](https://github.com/BlockRunAI/awesome-OpenClaw-Money-Maker) | NOASSERTION | `f74384660d7d78f3d077ead7b40eec9948e6c71c` | REFERENCE_ONLY |
| [`openclaw-trade/openclaw-trading-assistant`](https://github.com/openclaw-trade/openclaw-trading-assistant) | Apache-2.0 | `32030bdd268315bb70d07c7755f28d07de8e8552` | SANDBOX_ONLY |
| [`ccxt-rest/ccxt-rest`](https://github.com/ccxt-rest/ccxt-rest) | MIT | `6c1ae031bdfbf490e69ea0498eac97a4f6218ff0` | TOOLCHAIN_ONLY |
| [`ErTasselli/OpenTerminal`](https://github.com/ErTasselli/OpenTerminal) | MIT | `aed097c680cd8ec1c391ae06966babe7d6d91fc6` | REFERENCE_ONLY |
| [`OpenCoworkAI/open-cowork`](https://github.com/OpenCoworkAI/open-cowork) | MIT | `e2a29fca4a6c7f3b6f48412b892d94d2ac9dd20b` | SANDBOX_ONLY |
| [`arabold/docs-mcp-server`](https://github.com/arabold/docs-mcp-server) | MIT | `c180d7c2679d7886d14d42eed36a827d9befe5d3` | TOOLCHAIN_ONLY |
| [`aipoch/open-science`](https://github.com/aipoch/open-science) | Apache-2.0 | `dd8d5a19b3b67f3c01ee3af1edc1411bb34de1f0` | SANDBOX_ONLY |
| [`doobidoo/mcp-memory-service`](https://github.com/doobidoo/mcp-memory-service) | Apache-2.0 | `3b2b0cbf16cdb313aae460d83480313936a7ce55` | SANDBOX_ONLY |
| [`LING71671/open-reverselab`](https://github.com/LING71671/open-reverselab) | GPL-3.0 | `49abe85e73bfc29d9286204405570af6a5f8bb1d` | REFERENCE_ONLY |
| [`OpenOSINT/OpenOSINT`](https://github.com/OpenOSINT/OpenOSINT) | MIT | `c59f196f163e927f38e63ea716f5b5fe918524b3` | SANDBOX_ONLY |
| [`FireRedTeam/FireRed-OpenStoryline`](https://github.com/FireRedTeam/FireRed-OpenStoryline) | Apache-2.0 | `c9e945215586f45c12a61c1951ee9a8e9c43a027` | REFERENCE_ONLY |
| [`microsoft/mcp-for-beginners`](https://github.com/microsoft/mcp-for-beginners) | MIT | `ca9e0b559f90d59327bb4964946e538f1f613788` | REFERENCE_ONLY |
| [`idosal/git-mcp`](https://github.com/idosal/git-mcp) | Apache-2.0 | `c487a29895dcfcb5b672247e646426a56e2051c1` | TOOLCHAIN_ONLY |
| [`oomol-lab/open-connector`](https://github.com/oomol-lab/open-connector) | Apache-2.0 | `f9edd964568cf51e1669587d006d0c84163a517e` | SANDBOX_ONLY |
| [`open-metadata/OpenMetadata`](https://github.com/open-metadata/OpenMetadata) | Apache-2.0 | `38286a8af62e39573727bf879248f413ddca1b10` | SANDBOX_ONLY |
| [`MemPalace/mempalace`](https://github.com/MemPalace/mempalace) | MIT | `9b7805c58de50676786470fb59c0b74ab36b7526` | SANDBOX_ONLY |
| [`sashabaranov/go-openai`](https://github.com/sashabaranov/go-openai) | Apache-2.0 | `dd54fd29688ae9934688a2928be0abbd8647a812` | TOOLCHAIN_ONLY |
| [`RightNow-AI/openfang`](https://github.com/RightNow-AI/openfang) | Apache-2.0 | `acf2587e46be174c10200489c9a2d23a39a98aeb` | SANDBOX_ONLY |
| [`CopilotKit/OpenBot`](https://github.com/CopilotKit/OpenBot) | MIT | `12c3a69406b2ca32bcb117c0329c9c6d9359565d` | SANDBOX_ONLY |
| [`tinyhumansai/openhuman`](https://github.com/tinyhumansai/openhuman) | GPL-3.0 | `3f958ed2090ae142fcb31e918406bc265426a2bb` | SANDBOX_ONLY |
| [`every-app/open-seo`](https://github.com/every-app/open-seo) | MIT | `d7ea7852480601af9bc8870942af8311a410e567` | REFERENCE_ONLY |
| [`googleapis/mcp-toolbox`](https://github.com/googleapis/mcp-toolbox) | Apache-2.0 | `6d46c5f39df8088cd275d7efd5104149eb7c751d` | SANDBOX_ONLY |
| [`awslabs/mcp`](https://github.com/awslabs/mcp) | Apache-2.0 | `d534d0fa3c06838336ac1ed64e7114db0ba85e6f` | SANDBOX_ONLY |
| [`Ryze-AI-Adgent/open-seo-mcp-skills`](https://github.com/Ryze-AI-Adgent/open-seo-mcp-skills) | MIT | `cf7d8041a142f11c5abfffcdf2b423255cd18ca2` | REFERENCE_ONLY |
| [`PawanOsman/OpenCursor`](https://github.com/PawanOsman/OpenCursor) | MIT | `b4528f95ca5ab4cddf22bef3e19431fad00feb01` | SANDBOX_ONLY |
| [`CopilotKit/open-mcp-client`](https://github.com/CopilotKit/open-mcp-client) | NOASSERTION | `c8ea97b205ac860f08a4017dc36acba4d255b126` | SANDBOX_ONLY |
| [`rmyndharis/OpenWA`](https://github.com/rmyndharis/OpenWA) | MIT | `001fb1366620b791b9181ac2888b9a8c99976889` | SANDBOX_ONLY |
| [`bentoml/OpenLLM`](https://github.com/bentoml/OpenLLM) | Apache-2.0 | `ec2355ce1a75176164c451cbb7592b3046531540` | SANDBOX_ONLY |
| [`koreainvestment/open-trading-api`](https://github.com/koreainvestment/open-trading-api) | NOASSERTION | `2077773a69a428daf63e148182511f068cc45de3` | SANDBOX_ONLY |
| [`microsoft/OpenAPI.NET`](https://github.com/microsoft/OpenAPI.NET) | MIT | `00b56754355ded8221b97e067beb6ef2915b9346` | TOOLCHAIN_ONLY |
| [`open-telemetry/opentelemetry-js`](https://github.com/open-telemetry/opentelemetry-js) | Apache-2.0 | `7d2455e76ff2dd9d1ffae008d0682a49af4c55f3` | TOOLCHAIN_ONLY |
| [`APIs-guru/openapi-directory`](https://github.com/APIs-guru/openapi-directory) | CC0-1.0 | `f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49` | REFERENCE_ONLY |
| [`OpenAPITools/openapi-generator`](https://github.com/OpenAPITools/openapi-generator) | Apache-2.0 | `30f13393e78e9bc2ccbfafcd9398f1b0e8d415a2` | TOOLCHAIN_ONLY |
| [`openai/openai-openapi`](https://github.com/openai/openai-openapi) | MIT | `d156763a484eb247e116e0ea345e16344b0049ba` | TOOLCHAIN_ONLY |
| [`open-telemetry/opentelemetry-python`](https://github.com/open-telemetry/opentelemetry-python) | Apache-2.0 | `2fa016b27d9b817aee88ea58be1bd0bc10fd2a40` | TOOLCHAIN_ONLY |
| [`MacPaw/OpenAI`](https://github.com/MacPaw/OpenAI) | MIT | `75b91848dbd326313a2bf60f9833da2ebc9c0287` | TOOLCHAIN_ONLY |
| [`openai/openai-cookbook`](https://github.com/openai/openai-cookbook) | MIT | `5bd6cb40b6b84b69b2032d810610aa85064102df` | REFERENCE_ONLY |
| [`open-webui/open-webui`](https://github.com/open-webui/open-webui) | NOASSERTION | `91ea4e3421d1d8069f13d4a463fcb5986d94ea60` | SANDBOX_ONLY |
| [`OAI/OpenAPI-Specification`](https://github.com/OAI/OpenAPI-Specification) | Apache-2.0 | `8273770d983c99bb07b389d1706a9f8312ced503` | REFERENCE_ONLY |
| [`open-telemetry/opentelemetry-go`](https://github.com/open-telemetry/opentelemetry-go) | Apache-2.0 | `567abee176cb8ccc57a62b2b877a9b75e8abc3a7` | TOOLCHAIN_ONLY |
| [`openai/openai-node`](https://github.com/openai/openai-node) | Apache-2.0 | `bb024d41522d0b5a6b6c64055471111068811ccd` | TOOLCHAIN_ONLY |
| [`openmrs/openmrs-core`](https://github.com/openmrs/openmrs-core) | NOASSERTION | `d4348493a00571bd9e3adea68e8ede99428ddad8` | REFERENCE_ONLY |

## Priority findings from selected source review

### 1. Trading engines, live execution and broker MCPs — no integration approved

- **[FlintTrade](https://github.com/navaneeshnagarajan/FlintTrade)** — self-hosted trading platform; GitHub metadata reports AGPL-3.0. Recent workflows titled Supply Chain, Toolchain freshness and Node release key freshness succeeded on SHA `43a6b0b6bb215a1b64a61ba5425cfa77db9085db`, which differs from the inspected pin `a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d`. Do not present those runs as exact-pin validation. License obligations and the live-order boundary need review.
- **[OpenTrader](https://github.com/euriska/opentrader)** — multi-broker platform with LLM signals, scheduled execution and live-account support. README describes authentication middleware and encrypted database storage for API keys, but those claims are not an independent security audit. CI and release workflows passed on pinned SHA `d430a4448ebd7002e77d3996e678cf752edecfdd`. It remains a research reference only; never supply production credentials or route AURELIA orders through it.
- **[OpenMM MCP](https://github.com/QBT-Labs/openmm-mcp)** — MCP tools include crypto market/account/trading functions and a wallet/exchange credential vault. README also documents an environment-variable configuration path, so deployment must audit every credential path, vault access controls, socket permissions, transaction confirmation, and tool authorization. CI passed at pinned SHA `7f1036837d3100625f750e6bd7801534641c2295`; that does not validate custody or order safety. Keep disabled for live use.
- **[Blave Agent](https://github.com/Blave-TW/blave-agent)** — local desktop agent for backtests and live exchange automation. README says withdrawal-enabled keys are refused where detectable, but explicitly notes that Gate.io permissions may not be reported and must be checked manually. This is not an adequate substitute for isolated least-privilege credentials and independent risk controls. Desktop workflow passed on pinned SHA `effbc4bffbece9da445bdc70bbff590f8c91cf38`; no runtime or live-trading test performed.
- **[OpenEtradeMcp](https://github.com/kerryjiang/OpenEtradeMcp)** — exposes E*TRADE API operations, including order placement/modification/cancellation. README advertises a sandbox and optional MCP elicitation confirmation. Confirm that the client enforces elicitation and that direct API/tool paths cannot bypass it; secrets must not be placed in tracked MCP configuration. Source is reference-only for AURELIA.
- **[WyckoffTradingAgent](https://github.com/YoungCan-Wang/WyckoffTradingAgent)** — AGPL-3.0 Wyckoff analysis, screening, signals and MCP workflows. The latest observed CI success was on SHA `b98edd44e3b58223fd6e9e557fae5a22c0450098`, not inspected pin `9e848396975062ba22eb76185405728c85a50022`; the observed PyPI patch-release runs on the inspected SHA were skipped. It is not validated for AURELIA instruments or Deriv synthetic markets. Signals and claimed data repairs are not evidence of positive expectancy.
- **[PineForge Engine](https://github.com/pineforge-4pass/pineforge-engine)** — C++ backtest/forward-execution engine with Pine Script compatibility. CI passed on the inspected SHA `3fc010a8bb6cb460302c9ac6c34e7bba2e548f89). Its reported TradingView parity checks are software-semantic comparisons, not proof of profitability, realistic broker fills, no-lookahead, or Deriv compatibility. Promising candidate for offline research only after independent parity and cost tests.
- **[MT5-Quant](https://github.com/masdevid/mt5-quant)** — MCP workflow for MetaTrader 5 compilation, backtesting and analytics. CodeQL and dependency-review workflows succeeded on SHA `4e698abd4fe736261b3ea1ea8f67e3aaf37ecff7`, while the Rust workflow failed on that same SHA. Those are not the inspected pin `2a6cd8015a246032a286864d131309a0094c2d17`; current-pin build/test status remains unverified. Treat as tooling research only.
- **[Oracle3](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent)** — prediction-market research and paper/live venue adapters for Kalshi/Polymarket, with fees and pre-trade risk limits described in README. Pytest, Ruff and docs workflows passed at inspected SHA `267fb7c48dae7c4ff8922c02a3a223443e51bf0b`. That is useful project CI evidence, not a review of financial risk, venue execution or profitability. Its markets and settlement semantics do not transfer to Deriv synthetic indices.
- **[Wyckoff/stock MCP](https://github.com/Open-Agent-Tools/open-stocks-mcp)**, **[ChatGPT Trading Strategy Assistant](https://github.com/maghdam/chatgpt-trading-strategy-assistant)**, **[Bitget Agent Hub](https://github.com/Bitget-AI/agent_hub)**, **[Superior Skills](https://github.com/Superior-Trade/superior-skills)**, **[OpenTraderWorld](https://github.com/G-OTW/OpenTraderWorld)**, **[Noraz Agent](https://github.com/mogons/noraz-agent)**, **[OpenClaw Trading Assistant](https://github.com/openclaw-trade/openclaw-trading-assistant)**, **[CCXT REST](https://github.com/ccxt-rest/ccxt-rest)**, and **[Korea Investment Open Trading API](https://github.com/koreainvestment/open-trading-api)** are not cleared for execution. Their data, API or research patterns may be useful after individual review. CCXT REST is especially stale (repository metadata last pushed in 2023; no recent active maintenance established).
- **[LuxAlgo Edge Stats](https://github.com/LuxAlgo/edge-stats)** is the strongest research-method candidate in this set: local conditional-outcome statistics with sample sizes and confidence intervals. It still requires independent leakage, multiple-testing, sample-selection, regime, and transaction-cost validation before any statistic becomes an AURELIA signal.
- **[OpenTerminal](https://github.com/ErTasselli/OpenTerminal)** describes a dashboard based on free public market data; potentially useful as a UI/reference, not a trading engine or verified feed.
- **[OpenFinClaw CLI](https://github.com/mirror29/openfinclaw-cli)** and **[Awesome OpenClaw Money Maker](https://github.com/BlockRunAI/awesome-OpenClaw-Money-Maker)** are not cleared for automated installation. One is a community agent/quant workflow and the other is a curated list: links and skills in a list are untrusted inputs, not vetted dependencies.

### 2. MCP payments, connectors, memory and general agent runtimes

- **[modelcontextprotocol.name](https://github.com/nirholas/modelcontextprotocol.name)** advertises payment facilitation and DeFi/financial MCP access. Root README states root repository content is **all rights reserved**, while the nested `x402-facilitator/` has a separate MIT license. Do not copy the root or assume the whole repository is MIT. Crypto/payment tool exposure is high risk and not relevant to AURELIA's execution plane.
- **[Goose](https://github.com/aaif-goose/goose)**, **[OpenFang](https://github.com/RightNow-AI/openfang)**, **[OpenHuman](https://github.com/tinyhumansai/openhuman)**, **[OpenCowork](https://github.com/OpenCoworkAI/open-cowork)**, **[OpenBot](https://github.com/CopilotKit/OpenBot)**, **[OpenCursor](https://github.com/PawanOsman/OpenCursor)** and **[OpenLLM](https://github.com/bentoml/OpenLLM)** have potential roles in agent or inference tooling. They must be run only in constrained environments. Agent runtime features, shell access, browser access, workspace mounts, plugins, and custom tools can expand the attack surface; no such runtime is approved for production here.
- **[Open Connector](https://github.com/oomol-lab/open-connector)** advertises an auth gateway for many SaaS providers. Its broad OAuth/token scope and provider coverage require per-connector scopes, tenant isolation, token storage review, callback validation, revocation testing and audit logging before use.
- **[Google MCP Toolbox](https://github.com/googleapis/mcp-toolbox)** and **[AWS MCP](https://github.com/awslabs/mcp)** are plausible toolchain references for database/cloud access, but must use read-only, narrowly scoped identities by default. No broad cloud-admin or production database permissions for agents.
- **[MCP Memory Service](https://github.com/doobidoo/mcp-memory-service)** and **[MemPalace](https://github.com/MemPalace/mempalace)** need tenant isolation, retention/deletion, source provenance, memory-poisoning controls, and secret filtering before any persistence of AURELIA research. No production secrets or account data should enter shared agent memory.
- **[Evolution API](https://github.com/evolution-foundation/evolution-api)** and **[OpenWA](https://github.com/rmyndharis/OpenWA)** are messaging/WhatsApp gateways, not trading dependencies. License metadata for Evolution API is NOASSERTION. Before any notification-only trial, assess authentication, webhook signature verification, session/token storage, tenant isolation and inbound-command authorization. Do not allow chat messages to authorize trading.
- **[Synter MCP](https://github.com/Synter-Media-AI/mcp-server)** is an advertising-platform management tool, unrelated to AURELIA's trading system. Keep separate from trading credentials and operations.
- **[OpenOSINT](https://github.com/OpenOSINT/OpenOSINT)** is explicitly for authorized OSINT/security research. **[Open ReverseLab](https://github.com/LING71671/open-reverselab)** is reverse-engineering tooling. Neither belongs in the trading runtime; use only in isolated, authorized research environments.
- **[Open Science](https://github.com/aipoch/open-science)**, **[OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline)**, **[Open SEO](https://github.com/every-app/open-seo)**, **[Ryze SEO MCP skills](https://github.com/Ryze-AI-Adgent/open-seo-mcp-skills)**, **[OpenMRS](https://github.com/openmrs/openmrs-core)**, and the general OpenAPI/MCP curriculum are outside the AURELIA trading runtime. Use only for their specific research, education, marketing, or product purposes.

### 3. SDKs, specifications, API catalogues and observability

- **[OpenAI Python](https://github.com/openai/openai-python)**, **[OpenAI Node](https://github.com/openai/openai-node)**, **[go-openai](https://github.com/sashabaranov/go-openai)** and **[MacPaw/OpenAI Swift](https://github.com/MacPaw/OpenAI)** are SDK candidates; prefer official SDKs for supported languages and pin versions. They are not agent supervisors or risk controls.
- **[OpenAI OpenAPI](https://github.com/openai/openai-openapi)**, **[OpenAPI Specification](https://github.com/OAI/OpenAPI-Specification)**, **[OpenAPI Generator](https://github.com/OpenAPITools/openapi-generator)**, **[OpenAPI.NET](https://github.com/microsoft/OpenAPI.NET)**, **[API Directory](https://github.com/APIs-guru/openapi-directory)** and **[GitMCP](https://github.com/idosal/git-mcp)** can support contract-driven integration and documentation. Generated clients still require review of authentication, retries, rate limits, error semantics and idempotency; specs do not establish the behavior of a live broker.
- **[OpenAI Cookbook](https://github.com/openai/openai-cookbook)** and **[MCP for Beginners](https://github.com/microsoft/mcp-for-beginners)** are learning/reference material, not production assurance.
- **[OpenTelemetry JS](https://github.com/open-telemetry/opentelemetry-js)**, **[Python](https://github.com/open-telemetry/opentelemetry-python)** and **[Go](https://github.com/open-telemetry/opentelemetry-go)** are suitable observability candidates after instrumentation review. Ensure spans/logs never contain tokens, passwords, private account data, full prompts with secrets, or broker credentials.
- **[OpenMetadata](https://github.com/open-metadata/OpenMetadata)** is a broad data-context/catalog platform and likely excessive for the current constrained environment. Do not provision infrastructure or databases for it without an explicit cost/security decision.
- **[OpenAI Gemini proxy](https://github.com/PublicAffairs/openai-gemini)** is an API proxy candidate only. Before deployment review upstream API-key handling, user authentication, quotas, billing abuse, request/response logging, model mapping, and error propagation. MIT metadata is not a deployment security review.
- **[Open WebUI](https://github.com/open-webui/open-webui)** has NOASSERTION in the queried GitHub license metadata; do not assume a license from the repository name or product branding. Review license and auth configuration before any redistribution/deployment.

## CI evidence sampled

The following public GitHub Actions runs were observed; they are not substitutes for source review or isolated reproduction:

- FlintTrade workflow successes: [Supply Chain](https://github.com/navaneeshnagarajan/FlintTrade/actions/runs/39033855095), [Toolchain freshness](https://github.com/navaneeshnagarajan/FlintTrade/actions/runs/39033855063), [Node release key freshness](https://github.com/navaneeshnagarajan/FlintTrade/actions/runs/39033855199) ran on SHA `43a6b0b6bb215a1b64a61ba5425cfa77db9085db`, not the inspected pin.
- OpenTrader CI and release: [CI](https://github.com/euriska/opentrader/actions/runs/29702170523), [release](https://github.com/euriska/opentrader/actions/runs/29702175213) succeeded at its pinned SHA.
- OpenMM MCP CI succeeded at its pinned SHA: [run](https://github.com/QBT-Labs/openmm-mcp/actions/runs/34376777368).
- Wyckoff CI passed on a prior SHA; patch release skipped at the inspected SHA: [CI](https://github.com/YoungCan-Wang/WyckoffTradingAgent/actions/runs/39027592466), [release attempt](https://github.com/YoungCan-Wang/WyckoffTradingAgent/actions/runs/39028053765).
- PineForge CI passed at its inspected SHA: [run](https://github.com/pineforge-4pass/pineforge-engine/actions/runs/39038063971).
- Oracle3 pytest passed at its inspected SHA: [run](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/actions/runs/38190241873).
- MT5-Quant CodeQL and dependency review passed, but Rust CI failed on SHA `4e698abd4fe736261b3ea1ea8f67e3aaf37ecff7`, not the inspected pin: [CodeQL](https://github.com/masdevid/mt5-quant/actions/runs/38632841699), [dependency review](https://github.com/masdevid/mt5-quant/actions/runs/38632841617), [Rust failure](https://github.com/masdevid/mt5-quant/actions/runs/38632841608).
- Blave desktop Windows workflow passed at its inspected SHA: [run](https://github.com/Blave-TW/blave-agent/actions/runs/39029320304).

## Cross-agent work allocation

- **ClaudeCode:** implementation-level source/dependency inspection and isolated test plans only; no production changes without review.
- **ChatGPT:** architecture fit, evidence synthesis, source/claim reconciliation, and this intake report.
- **KimiK3:** quantitative-method review for Edge Stats, PineForge, Wyckoff, Oracle3 and other trading candidates; require leakage-resistant OOS, cost/latency modelling, calibration, and instrument-specific validity.
- **JEV:** independent review of exact pinned SHAs and reproduced CI/security results; cannot self-approve.
- **GoogleAgentSkills:** sandbox, OAuth/token, remote-code, network-egress and least-privilege threat models.
- **GLM:** evidence manifests, hashes, license metadata consistency, duplicate detection and stale/missing-artifact reporting.
- **GrokBot:** queue coordination and blocker/status reporting only.
- **Dev:** isolated runtime/deployment tasks only when an authorized persistent host is available. No paid resource creation.
- **AURELIA deterministic risk plane:** remains the only risk/release authority. No LLM or external MCP may modify LIVE_LOCK, read production secrets, authorize capital, or submit broker transactions.

## Duplicate handling and registry status

The user supplied 69 URLs representing 67 unique repositories; `RightNow-AI/openfang` and `6551Team/opennews-mcp` were each repeated once. All 67 unique repositories were verified as present in `config/external_repo_federation.json`, with pinned commit identifiers and non-capital modes. The registry is an intake control, not proof of a complete scan.

## Release decision and required next steps

**Status: INTAKE COMPLETE; SECURITY/INTEGRATION REVIEW PENDING.** No candidate is approved for direct capital-plane integration. Do not merge this PR solely because the documentation and metadata triage exist.

For any candidate to advance:
1. Confirm the default-branch ref SHA and review the exact source at that SHA.
2. Review license/NOTICE and model/data licensing separately.
3. Build in a disposable, non-privileged runner; produce SBOM, dependency/security and secret-scan evidence.
4. Test auth, tool permissions, filesystem/network boundaries, credential handling, idempotency, retry/failure semantics and logging redaction.
5. For trading candidates, use sandbox/paper execution only and independently validate market-data provenance, realistic fees/spread/slippage/latency, no-lookahead, walk-forward/OOS, calibration, drawdown and recovery.
6. Keep agent-generated signals advisory. AURELIA's existing fail-closed live release gates remain mandatory, including fresh broker evidence, human approval and the required 3,600-second soak.

No third-party source was copied into AURELIA's execution runtime, no secrets were accessed, and no live orders were submitted.
