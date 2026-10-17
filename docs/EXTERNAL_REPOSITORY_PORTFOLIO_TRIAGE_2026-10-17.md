# External Repository Portfolio Triage — 2026-10-17

## Executive summary

Processed 67 distinct repository URLs (the supplied list had two duplicates). Resolved GitHub metadata and default-branch commit SHAs, and registered conservative intake classifications in AURELIA's existing external-source registry.

**No repository is approved for direct integration into AURELIA's capital/execution plane.** All entries are `SOURCE_TRIAGE_ONLY`: metadata and selected README/source material, not completed isolated clone/build, full source review, SBOM, dependency/secret/malware scan, legal review, or runtime test.

Registry after update: 366 entries. Mode counts: `SANDBOX_ONLY` 172, `TOOLCHAIN_ONLY` 58, `RESEARCH_ONLY` 64, `REFERENCE_ONLY` 72. The new entries all set `capital_authority=false` and `physical_runtime_install=NOT_CLAIMED`.

## Safety and evidence boundaries

- No external source was copied into runtime paths, no package installed, no paid infrastructure created, no credentials accessed, and no broker transaction submitted.
- SHAs below are commit pins from GitHub's commits API as checked on 2026-10-17, not signatures or trust attestations.
- GitHub license metadata is not legal advice; `NOASSERTION` means no SPDX license was reported. Check subdirectories, dependencies, models and bundled artifacts separately.
- Agent assignments in the registry are proposed review ownership, not proof of live agent connections or independent execution.
- External README/tool descriptions are untrusted input. External agents may not change `LIVE_LOCK`, access production secrets, authorize capital or submit orders.

## Priority A — Trading, broker, wallet, and order-capable projects

- **FlintTrade**: current README says beta/not production-ready and describes broker paths as evidence-gated; AGPL-3.0. Research only. Review install scripts, gateway, auth, live guards and license obligations. [Repository](https://github.com/navaneeshnagarajan/FlintTrade) · [Current source review](https://github.com/navaneeshnagarajan/FlintTrade)
- **OpenTrader**: advertises multi-broker live execution, encrypted credential storage, auth middleware and circuit breakers. These are claims, not independently verified controls. Require crypto/auth review, order lifecycle, idempotency, reconciliation, dependency scans and fail-closed tests. [Repository](https://github.com/euriska/opentrader)
- **OpenMM MCP**: account/trading/strategy tools and wallet/exchange credentials. Disposable testnet only; no AURELIA credentials. [Repository](https://github.com/QBT-Labs/openmm-mcp)
- **Blave Agent**: live exchange trading plus backtest, walk-forward and parameter scans; compare workflows only until strategy and security evidence is independently replicated. [Repository](https://github.com/Blave-TW/blave-agent)
- **OpenEtradeMcp**: order place/cancel/modify tools and advertised confirmation gate; test bypass paths and direct-client behavior. [Repository](https://github.com/kerryjiang/OpenEtradeMcp)
- **WyckoffTradingAgent**: AGPL-3.0 research/screener/MCP; validate data provenance, point-in-time availability, survivorship and OOS. [Repository](https://github.com/YoungCan-Wang/WyckoffTradingAgent)
- **Pineforge Engine**: possible deterministic backtest comparator; independently reproduce corpus results; a matching trade list does not establish edge or Deriv compatibility. [Repository](https://github.com/pineforge-4pass/pineforge-engine)
- **Edge Stats**: potential conditional-probability helper; audit event definitions, multiple testing, confidence intervals and leakage. [Repository](https://github.com/LuxAlgo/edge-stats)
- **MT5-Quant**: MCP tools can compile/run expert advisors; sandbox arbitrary code. MT5 behavior does not automatically transfer to Deriv synthetic indices. [Repository](https://github.com/masdevid/mt5-quant)
- **Oracle3**: prediction-market fee-adjusted research and separate paper/live engine; venue settlement, liquidity and fees are not portable to AURELIA. [Repository](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent)
- **Bitget Agent Hub**: official exchange toolkit advertising 89 UTA operations; demo/read-only review only. [Repository](https://github.com/Bitget-AI/agent_hub)
- **Superior Skills**: strategy build/backtest/deploy agent skills; inspect every tool schema and disable live routes. [Repository](https://github.com/Superior-Trade/superior-skills)
- **OpenTraderWorld**: source-available/Fair Source metadata; legal clearance and MCP/order review required. [Repository](https://github.com/G-OTW/OpenTraderWorld)
- **Noraz Agent**: wallets, DEX research and copy-trading; no capital integration. [Repository](https://github.com/mogons/noraz-agent)
- **Open Stocks MCP**: verify endpoint read-only status, authentication and provenance. [Repository](https://github.com/Open-Agent-Tools/open-stocks-mcp)
- **ChatGPT Trading Strategy Assistant**: cTrader-backed order placement; mock-only until auth, schema, idempotency and reconciliation tests pass. [Repository](https://github.com/maghdam/chatgpt-trading-strategy-assistant)
- **OpenClaw Trading Assistant**: autonomous Hyperliquid trading/social-news inputs; older source and no approval for execution. [Repository](https://github.com/openclaw-trade/openclaw-trading-assistant)
- **Korea Investment Open Trading API**: no license metadata and broker-specific semantics; sandbox only. [Repository](https://github.com/koreainvestment/open-trading-api)
- **OpenFinClaw CLI**: quant agent; license absent and installer/tool permissions need review. [Repository](https://github.com/mirror29/openfinclaw-cli)
- **modelcontextprotocol.name**: root content is all-rights-reserved while a subdirectory has its own MIT license; money-moving DeFi/payment tools must not be granted AURELIA access. [Repository](https://github.com/nirholas/modelcontextprotocol.name)

## Priority B — Agent execution, memory, connectors, MCP

Goose, OpenFang, OpenHuman, OpenCowork, OpenCursor, OpenBot, OpenLLM and OpenWebUI have broad agent, desktop, serving or UI surfaces. Inspect actual shell/file/network permissions, auth defaults, extension trust, model remote code and secrets handling. OpenHuman is GPL-3.0; OpenWebUI reports `NOASSERTION` metadata.

Google MCP Toolbox, AWS MCP, Open Connector, OpenMetadata, MCP Memory Service and MemPalace need least-privilege, retention/deletion, prompt-injection, memory-poisoning, query limits, and audit logging review. Evolution API and OpenWA require session isolation, webhook validation, rate limiting and token redaction. A confirmation UI is defense in depth, not a substitute for a deterministic execution firewall. OpenOSINT must be used only within authorized scopes; Open ReverseLab is GPL-3.0 and unrelated to AURELIA runtime.

## Priority C — SDKs, API specs, observability, documentation

Most relevant toolchain/reference candidates: official `openai/openai-python`, `openai/openai-node`, `openai/openai-openapi`; `microsoft/OpenAPI.NET`; `OpenAPITools/openapi-generator`; `OAI/OpenAPI-Specification`; `open-telemetry/opentelemetry-{js,python,go}`; `sashabaranov/go-openai`; `MacPaw/OpenAI`; `arabold/docs-mcp-server`; `idosal/git-mcp`; and `microsoft/mcp-for-beginners`. Pin versions, contract-test APIs, and redact tokens/account data in telemetry. Community SDKs are not official OpenAI clients.

## Priority D — Reference-only

Curated lists, examples, education, dashboards, SEO, video, reverse-engineering and healthcare repos remain references, not runtime dependencies. This includes OpenAI Cookbook, OpenTerminal, OpenAPI Directory/specification, MCP for Beginners, SEO projects, FireRed-OpenStoryline and OpenMRS Core. OpenMRS and other `NOASSERTION` repositories need separate license review before any redistribution.

## Full ledger

| Repository | Pinned commit | GitHub license metadata | Mode | Initial finding |
|---|---|---|---|---|
| [`evolution-foundation/evolution-api`](https://github.com/evolution-foundation/evolution-api) | `fa09d37892cdbb1d65a250155d293d92230c5b30` | NOASSERTION | SANDBOX_ONLY | Messaging gateway; isolated test only. |
| [`PublicAffairs/openai-gemini`](https://github.com/PublicAffairs/openai-gemini) | `61a83bd9d0def59811624b6ae7d8213a231185d0` | MIT | SANDBOX_ONLY | Review auth, logging and data routing. |
| [`openai/openai-python`](https://github.com/openai/openai-python) | `bfada5040b0171cd0ae61aefae8c78fcf83c804a` | Apache-2.0 | TOOLCHAIN_ONLY | Official SDK; pin version and contract-test. |
| [`nirholas/modelcontextprotocol.name`](https://github.com/nirholas/modelcontextprotocol.name) | `f945ce4d75c6de834071c18e11e0a38a44f5862b` | NOASSERTION | SANDBOX_ONLY | Root all-rights-reserved; subdirectory license differs; payment tools isolated. |
| [`navaneeshnagarajan/FlintTrade`](https://github.com/navaneeshnagarajan/FlintTrade) | `a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d` | AGPL-3.0 | RESEARCH_ONLY | Beta/not production-ready; broker paths evidence-gated. |
| [`euriska/opentrader`](https://github.com/euriska/opentrader) | `d430a4448ebd7002e77d3996e678cf752edecfdd` | Apache-2.0 | RESEARCH_ONLY | Live execution; audit auth, order lifecycle and secrets. |
| [`QBT-Labs/openmm-mcp`](https://github.com/QBT-Labs/openmm-mcp) | `7f1036837d3100625f750e6bd7801534641c2295` | MIT | SANDBOX_ONLY | Account/trading tools and wallet credentials. |
| [`Synter-Media-AI/mcp-server`](https://github.com/Synter-Media-AI/mcp-server) | `000d446f465687a5a1249a268e9bfa3f6a3e597d` | MIT | SANDBOX_ONLY | External write actions; scope permissions/tokens. |
| [`Blave-TW/blave-agent`](https://github.com/Blave-TW/blave-agent) | `effbc4bffbece9da445bdc70bbff590f8c91cf38` | Apache-2.0 | RESEARCH_ONLY | Live exchange support; research only pending audit. |
| [`kerryjiang/OpenEtradeMcp`](https://github.com/kerryjiang/OpenEtradeMcp) | `a53a007c1dba329e79669adbc58a3552a2f4f74e` | Apache-2.0 | SANDBOX_ONLY | Place/cancel/modify; test confirmation gate bypass. |
| [`YoungCan-Wang/WyckoffTradingAgent`](https://github.com/YoungCan-Wang/WyckoffTradingAgent) | `9e848396975062ba22eb76185405728c85a50022` | AGPL-3.0 | RESEARCH_ONLY | Validate provenance, point-in-time data and OOS. |
| [`pineforge-4pass/pineforge-engine`](https://github.com/pineforge-4pass/pineforge-engine) | `3fc010a8bb6cb460302c9ac6c34e7bba2e548f89` | Apache-2.0 | RESEARCH_ONLY | Replicate backtest claims independently. |
| [`LuxAlgo/edge-stats`](https://github.com/LuxAlgo/edge-stats) | `a48259887962d0f67a27d2b0815e2df9a52efca5` | MIT | RESEARCH_ONLY | Audit sampling, multiple tests, confidence intervals and leakage. |
| [`mirror29/openfinclaw-cli`](https://github.com/mirror29/openfinclaw-cli) | `f48e8117eb0364a60b4f780361063befc97e5b33` | NOASSERTION | SANDBOX_ONLY | License absent; inspect installer/tool permissions. |
| [`masdevid/mt5-quant`](https://github.com/masdevid/mt5-quant) | `2a6cd8015a246032a286864d131309a0094c2d17` | MIT | SANDBOX_ONLY | Compile/run EA workflows; sandbox arbitrary code. |
| [`YichengYang-Ethan/oracle3-prediction-market-agent`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent) | `267fb7c48dae7c4ff8922c02a3a223443e51bf0b` | Apache-2.0 | RESEARCH_ONLY | Fee-adjusted research; audit venue rules and OOS. |
| [`Bitget-AI/agent_hub`](https://github.com/Bitget-AI/agent_hub) | `2551419578abff99baad19b018cab1a963c62306` | MIT | SANDBOX_ONLY | 89 exchange operations; demo/read-only review only. |
| [`Superior-Trade/superior-skills`](https://github.com/Superior-Trade/superior-skills) | `9d41db54b231f77e35610a73230eaeffcb456215` | MIT | SANDBOX_ONLY | Inspect each tool schema; disable live order routes. |
| [`G-OTW/OpenTraderWorld`](https://github.com/G-OTW/OpenTraderWorld) | `8df74511c2d1c86909188363c302b83814915793` | NOASSERTION | RESEARCH_ONLY | Source-available terms; legal/MCP audit required. |
| [`TokenRhythm/opensquilla`](https://github.com/TokenRhythm/opensquilla) | `d3f926c17e361b27f0410e6ea52526c9a2bcbb3d` | Apache-2.0 | SANDBOX_ONLY | Evaluate tool permissions and isolation. |
| [`mogons/noraz-agent`](https://github.com/mogons/noraz-agent) | `8f53497b2b47641de67692606053d4c5343bcfa6` | MIT | SANDBOX_ONLY | Wallet/DEX/copy trading; no capital integration. |
| [`Open-Agent-Tools/open-stocks-mcp`](https://github.com/Open-Agent-Tools/open-stocks-mcp) | `b50f61e275a412dd71ec5642cccca9206462724a` | Apache-2.0 | SANDBOX_ONLY | Verify auth, provenance and read-only behavior. |
| [`maghdam/chatgpt-trading-strategy-assistant`](https://github.com/maghdam/chatgpt-trading-strategy-assistant) | `809c30e92bb1b8e835a0c45ca673c80379b0b9a5` | MIT | SANDBOX_ONLY | Order placement; mock-only until safety tests. |
| [`6551Team/opennews-mcp`](https://github.com/6551Team/opennews-mcp) | `e329f36187e4a51a0878823e4fdd4d8f42134e80` | MIT | RESEARCH_ONLY | Verify timestamps, licensing and signal leakage. |
| [`aaif-goose/goose`](https://github.com/aaif-goose/goose) | `bfcc6ee6f1ee18d0c4c852a65c49b25f87ee40dc` | Apache-2.0 | SANDBOX_ONLY | Execution/editing agent; no secrets or broker tools. |
| [`BlockRunAI/awesome-OpenClaw-Money-Maker`](https://github.com/BlockRunAI/awesome-OpenClaw-Money-Maker) | `f74384660d7d78f3d077ead7b40eec9948e6c71c` | NOASSERTION | REFERENCE_ONLY | List only; no security endorsement. |
| [`openclaw-trade/openclaw-trading-assistant`](https://github.com/openclaw-trade/openclaw-trading-assistant) | `32030bdd268315bb70d07c7755f28d07de8e8552` | Apache-2.0 | SANDBOX_ONLY | Autonomous trading claims; older source, adversarial review. |
| [`ccxt-rest/ccxt-rest`](https://github.com/ccxt-rest/ccxt-rest) | `6c1ae031bdfbf490e69ea0498eac97a4f6218ff0` | MIT | TOOLCHAIN_ONLY | Last commit 2020; stale dependency/API risk. |
| [`ErTasselli/OpenTerminal`](https://github.com/ErTasselli/OpenTerminal) | `aed097c680cd8ec1c391ae06966babe7d6d91fc6` | MIT | REFERENCE_ONLY | Public-data dashboard reference only. |
| [`OpenCoworkAI/open-cowork`](https://github.com/OpenCoworkAI/open-cowork) | `e2a29fca4a6c7f3b6f48412b892d94d2ac9dd20b` | MIT | SANDBOX_ONLY | Audit actual sandbox and host permissions. |
| [`arabold/docs-mcp-server`](https://github.com/arabold/docs-mcp-server) | `c180d7c2679d7886d14d42eed36a827d9befe5d3` | MIT | TOOLCHAIN_ONLY | Pin docs origins; prompt-injection defense. |
| [`aipoch/open-science`](https://github.com/aipoch/open-science) | `dd8d5a19b3b67f3c01ee3af1edc1411bb34de1f0` | Apache-2.0 | SANDBOX_ONLY | Sandbox Python/R execution and connectors. |
| [`doobidoo/mcp-memory-service`](https://github.com/doobidoo/mcp-memory-service) | `3b2b0cbf16cdb313aae460d83480313936a7ce55` | Apache-2.0 | SANDBOX_ONLY | Review retention, access, deletion and poisoning. |
| [`LING71671/open-reverselab`](https://github.com/LING71671/open-reverselab) | `49abe85e73bfc29d9286204405570af6a5f8bb1d` | GPL-3.0 | REFERENCE_ONLY | Unrelated; authorized use and license review. |
| [`OpenOSINT/OpenOSINT`](https://github.com/OpenOSINT/OpenOSINT) | `c59f196f163e927f38e63ea716f5b5fe918524b3` | MIT | SANDBOX_ONLY | Authorized scopes and data governance only. |
| [`FireRedTeam/FireRed-OpenStoryline`](https://github.com/FireRedTeam/FireRed-OpenStoryline) | `c9e945215586f45c12a61c1951ee9a8e9c43a027` | Apache-2.0 | REFERENCE_ONLY | Unrelated video workflow. |
| [`microsoft/mcp-for-beginners`](https://github.com/microsoft/mcp-for-beginners) | `ca9e0b559f90d59327bb4964946e538f1f613788` | MIT | REFERENCE_ONLY | Learning resource, not production evidence. |
| [`idosal/git-mcp`](https://github.com/idosal/git-mcp) | `c487a29895dcfcb5b672247e646426a56e2051c1` | Apache-2.0 | TOOLCHAIN_ONLY | Pin revisions; fetched text remains untrusted. |
| [`oomol-lab/open-connector`](https://github.com/oomol-lab/open-connector) | `f9edd964568cf51e1669587d006d0c84163a517e` | Apache-2.0 | SANDBOX_ONLY | Broad OAuth connectors; least privilege and audit. |
| [`open-metadata/OpenMetadata`](https://github.com/open-metadata/OpenMetadata) | `38286a8af62e39573727bf879248f413ddca1b10` | Apache-2.0 | SANDBOX_ONLY | Large data context platform; no immediate runtime need. |
| [`MemPalace/mempalace`](https://github.com/MemPalace/mempalace) | `9b7805c58de50676786470fb59c0b74ab36b7526` | MIT | SANDBOX_ONLY | Access control, retrieval isolation and poisoning review. |
| [`sashabaranov/go-openai`](https://github.com/sashabaranov/go-openai) | `dd54fd29688ae9934688a2928be0abbd8647a812` | Apache-2.0 | TOOLCHAIN_ONLY | Community client; pin and contract-test. |
| [`RightNow-AI/openfang`](https://github.com/RightNow-AI/openfang) | `acf2587e46be174c10200489c9a2d23a39a98aeb` | Apache-2.0 | SANDBOX_ONLY | Broad host/tool permissions; sandbox only. |
| [`CopilotKit/OpenBot`](https://github.com/CopilotKit/OpenBot) | `12c3a69406b2ca32bcb117c0329c9c6d9359565d` | MIT | SANDBOX_ONLY | Earlier review found unsafe single-user admin default; do not expose. |
| [`tinyhumansai/openhuman`](https://github.com/tinyhumansai/openhuman) | `3f958ed2090ae142fcb31e918406bc265426a2bb` | GPL-3.0 | SANDBOX_ONLY | Audit shell permissions and license obligations. |
| [`every-app/open-seo`](https://github.com/every-app/open-seo) | `d7ea7852480601af9bc8870942af8311a410e567` | MIT | REFERENCE_ONLY | Unrelated SEO application. |
| [`googleapis/mcp-toolbox`](https://github.com/googleapis/mcp-toolbox) | `6d46c5f39df8088cd275d7efd5104149eb7c751d` | Apache-2.0 | SANDBOX_ONLY | Read-only credentials, query limits and row controls. |
| [`awslabs/mcp`](https://github.com/awslabs/mcp) | `d534d0fa3c06838336ac1ed64e7114db0ba85e6f` | Apache-2.0 | SANDBOX_ONLY | Deny cloud writes; least-privilege credentials. |
| [`Ryze-AI-Adgent/open-seo-mcp-skills`](https://github.com/Ryze-AI-Adgent/open-seo-mcp-skills) | `cf7d8041a142f11c5abfffcdf2b423255cd18ca2` | MIT | REFERENCE_ONLY | Unrelated SEO skills; review remote endpoint if used. |
| [`PawanOsman/OpenCursor`](https://github.com/PawanOsman/OpenCursor) | `b4528f95ca5ab4cddf22bef3e19431fad00feb01` | MIT | SANDBOX_ONLY | Isolate IDE workspace, tools and extensions. |
| [`CopilotKit/open-mcp-client`](https://github.com/CopilotKit/open-mcp-client) | `c8ea97b205ac860f08a4017dc36acba4d255b126` | NOASSERTION | SANDBOX_ONLY | Latest commit 2025-04-22; establish maintenance posture. |
| [`rmyndharis/OpenWA`](https://github.com/rmyndharis/OpenWA) | `001fb1366620b791b9181ac2888b9a8c99976889` | MIT | SANDBOX_ONLY | Protect session credentials, webhook auth and logs. |
| [`bentoml/OpenLLM`](https://github.com/bentoml/OpenLLM) | `ec2355ce1a75176164c451cbb7592b3046531540` | Apache-2.0 | SANDBOX_ONLY | Isolate model downloads, remote code and ingress. |
| [`koreainvestment/open-trading-api`](https://github.com/koreainvestment/open-trading-api) | `2077773a69a428daf63e148182511f068cc45de3` | NOASSERTION | SANDBOX_ONLY | No license metadata; Korea-specific broker semantics. |
| [`microsoft/OpenAPI.NET`](https://github.com/microsoft/OpenAPI.NET) | `00b56754355ded8221b97e067beb6ef2915b9346` | MIT | TOOLCHAIN_ONLY | Review package and generated schema diffs. |
| [`open-telemetry/opentelemetry-js`](https://github.com/open-telemetry/opentelemetry-js) | `7d2455e76ff2dd9d1ffae008d0682a49af4c55f3` | Apache-2.0 | TOOLCHAIN_ONLY | Redact credentials/account data in telemetry. |
| [`APIs-guru/openapi-directory`](https://github.com/APIs-guru/openapi-directory) | `f04b8d0bcd39c52e1cf3ad7a5fe744709832ae49` | CC0-1.0 | REFERENCE_ONLY | Validate specs against authoritative broker docs. |
| [`OpenAPITools/openapi-generator`](https://github.com/OpenAPITools/openapi-generator) | `30f13393e78e9bc2ccbfafcd9398f1b0e8d415a2` | Apache-2.0 | TOOLCHAIN_ONLY | Generated code needs review. |
| [`openai/openai-openapi`](https://github.com/openai/openai-openapi) | `d156763a484eb247e116e0ea345e16344b0049ba` | MIT | TOOLCHAIN_ONLY | Official API schema; pin revision. |
| [`open-telemetry/opentelemetry-python`](https://github.com/open-telemetry/opentelemetry-python) | `2fa016b27d9b817aee88ea58be1bd0bc10fd2a40` | Apache-2.0 | TOOLCHAIN_ONLY | Filter sensitive fields and bound retention. |
| [`MacPaw/OpenAI`](https://github.com/MacPaw/OpenAI) | `75b91848dbd326313a2bf60f9833da2ebc9c0287` | MIT | TOOLCHAIN_ONLY | Community client, not official. |
| [`openai/openai-cookbook`](https://github.com/openai/openai-cookbook) | `5bd6cb40b6b84b69b2032d810610aa85064102df` | MIT | REFERENCE_ONLY | Examples only, not production hardening. |
| [`open-webui/open-webui`](https://github.com/open-webui/open-webui) | `91ea4e3421d1d8069f13d4a463fcb5986d94ea60` | NOASSERTION | SANDBOX_ONLY | License metadata NOASSERTION; review rights/auth. |
| [`OAI/OpenAPI-Specification`](https://github.com/OAI/OpenAPI-Specification) | `8273770d983c99bb07b389d1706a9f8312ced503` | Apache-2.0 | REFERENCE_ONLY | Specification reference only. |
| [`open-telemetry/opentelemetry-go`](https://github.com/open-telemetry/opentelemetry-go) | `567abee176cb8ccc57a62b2b877a9b75e8abc3a7` | Apache-2.0 | TOOLCHAIN_ONLY | Redact secrets and constrain trace export. |
| [`openai/openai-node`](https://github.com/openai/openai-node) | `bb024d41522d0b5a6b6c64055471111068811ccd` | Apache-2.0 | TOOLCHAIN_ONLY | Official JS/TS SDK; pin and contract-test. |
| [`openmrs/openmrs-core`](https://github.com/openmrs/openmrs-core) | `d4348493a00571bd9e3adea68e8ede99428ddad8` | NOASSERTION | REFERENCE_ONLY | Unrelated; license metadata NOASSERTION. |

## Promotion gates

1. Exact SHA and package/artifact hashes; inspect install/build scripts before execution.
2. Independent license/NOTICE review for code, dependencies, models and subdirectories.
3. Isolated build with no secrets, canonical-repo write access, broker credentials or live endpoints; restrict network egress.
4. SBOM, dependency vulnerability scan, secret scan, static/malware analysis where available, and retained evidence.
5. Permission matrix for each MCP tool, connector, shell command, file path, outbound endpoint and write-capable operation.
6. For trading code: deterministic risk tests, spread/fee/slippage/latency modeling, no-lookahead, walk-forward/OOS, calibration/drift, broker contract validation, idempotency/reconciliation, kill switch and independent review.
7. Promote registry mode only after evidence is attached and independently reviewed. CI green alone is not production certification.

**Disposition:** all 67 URLs are registered; none is approved for the capital plane. AURELIA's `LIVE_EXECUTION=BLOCKED` and `FINAL_EXECUTION_AUTHORIZATION=false` remain unchanged.
