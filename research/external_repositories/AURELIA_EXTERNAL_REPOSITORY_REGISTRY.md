# AURELIA External Repository Registry

This registry pins external repositories requested for AURELIA intelligence and engineering synchronization. It is deliberately not a dependency lockfile: external source is reviewed before any runtime adoption.

## Authority boundary

External repositories may inform research, engineering, QA, security, UI, and operational tooling. They cannot:

- acquire capital authority;
- submit or modify broker orders;
- read production secrets;
- mutate LIVE_LOCK or FINAL_EXECUTION_AUTHORIZATION;
- bypass Balance Truth, Risk Warden, Execution Firewall, reconciliation, or release gates;
- convert external strategy signals into live trades.

## Pinned sources

### ajaxorg/ace
- Pin: `62d5ffd789b4eb29ef7c1acc17554c91c745a307`
- Role: Command Center UI / Engineering
- Status: candidate
- Integration: research reference; use package-level Ace only if/when a browser editor is actually required
- Notes: Standalone embeddable JavaScript editor; BSD license. Do not vendor the full source tree into runtime.

### remorses/playwriter
- Pin: `525732a474a14224d46469c2b85737dbcdc23e07`
- Role: Browser Automation / Operations QA
- Status: candidate
- Integration: sandbox/ops tooling only
- Notes: Connects agents to a running browser and exposes Playwright-style automation. Never use it to bypass AURELIA auth, release gates, or broker controls.

### openinterpreter/openinterpreter
- Pin: `cc054cf52fa3585a3de50e0d4e0be6f9ee6677e8`
- Role: Engineering Agent / Research Orchestrator
- Status: candidate
- Integration: sandbox-only research and code-maintenance tooling
- Notes: Current repository is a large agent/coding monorepo. Do not grant shell execution or capital authority from it.

### morluto/rea
- Pin: `a45fe86a39b9e7a7c21e3665b6de4763cb72d782`
- Role: Security / Reverse Engineering
- Status: candidate
- Integration: sandbox-only investigation tooling
- Notes: Reverse-engineering MCP for binaries, applications and runtime behavior. Use for inspection, not production execution.

### hackingthemarkets/tradingview-binance-strategy-alert-webhook
- Pin: `ddb18c96416014067658557ff0d8df29213d6dcf`
- Role: Strategy Research / Webhook Pattern Research
- Status: research-only
- Integration: reference only
- Notes: TradingView-to-Binance alert webhook. Binance execution semantics must not be mapped directly into Deriv execution.

### jamesmawm/High-Frequency-Trading-Model-with-IB
- Pin: `8e96ade54a8e3eb94ead04827a846225ae122864`
- Role: Quant Research / Microstructure
- Status: research-only
- Integration: reference only
- Notes: Interactive Brokers HFT/pairs/mean-reversion example. Repository README explicitly warns components are outdated and likely not working as intended.

### blampe/IbPy
- Pin: `cba912d2ecc669b0bf2980357ea7942e49c0825e`
- Role: Quant Research / Legacy Broker Study
- Status: quarantine
- Integration: reference only; do not install
- Notes: Repository is archived and its README says it is superfluous for Python 3 because Interactive Brokers has an official Python API.

### nntaoli-project/goex
- Pin: `0a7d6619669ffc3164aa8fdceb545a64dc7f2cc4`
- Role: Crypto Exchange Abstraction Research
- Status: research-only
- Integration: reference only; no broker adapter import
- Notes: Go exchange wrapper currently documents OKX/Binance support. It is not a Deriv adapter and cannot authorize or submit AURELIA orders.

## Installation policy

The current AURELIA Python runtime contains only its required runtime dependency set. These repositories are therefore synchronized as pinned intelligence sources first, rather than being injected wholesale into the production runtime. This avoids dependency pollution, supply-chain drift, and accidental broker-authority inheritance.

A later runtime dependency may be admitted only through an explicit bounded adapter, tests, provenance pin, license/security review, and existing release gates.


### BerriAI/litellm
- Pin: `5e1c5c0bd17781a83b4368c38ebebcf7bc683fcb`
- Role: Multi-provider LLM gateway / orchestration infrastructure
- Mode: `SANDBOX_ONLY`
- Integration: architecture reference; no production runtime install in this sync
- Security: recent upstream advisories include critical/high issues. LiteLLM's March 2026 security notice documented compromised PyPI releases `1.82.7` and `1.82.8`; do not install those versions. Review current advisories and verify a pinned, signed release before any future adoption.
- Boundary: no access to Deriv credentials, no production secrets, no authority to change LIVE_LOCK or execute trades.

### LiteLLM-Labs/litellm-agent-control-plane
- Pin: `53bfd20e2fec51fc8f665fb614512c6b138367da`
- Role: Agent control-plane architecture
- Mode: `SANDBOX_ONLY`
- Integration: compare agent routing and provider-control patterns; cannot control AURELIA's deterministic capital plane.

### BerriAI/litellm-docs
- Pin: `4a73adff0a530b948b043b0fa64bf96d2cc7c4ce`
- Role: Official LiteLLM documentation
- Mode: `REFERENCE_ONLY`
- Integration: documentation/security-advisory lookup only.

### BerriAI/liteLLM-proxy
- Pin: `1ef69ae92bf22600f9a42d15e3b992e1010c9a7e`
- Role: Legacy proxy reference
- Mode: `REFERENCE_ONLY`
- Integration: older repository; not the preferred current upstream implementation.

### numman-ali/cc-mirror
- Pin: `e0e6f289c78ebe7f38bd8afcad92d28ea7e4f1e5`
- Role: Isolated Claude Code / custom-provider developer tooling
- Mode: `SANDBOX_ONLY`
- Integration: developer tooling research; never route production credentials through modified coding-agent binaries.

### BerriAI/litellm-pgvector
- Pin: `5bd8f3ab1fa9129e758a2c4b17ba1c6f3047ba24`
- Role: Vector-memory integration
- Mode: `SANDBOX_ONLY`
- Integration: retrieval architecture reference only; no production account data or secrets.

### LiteLLM-Labs/litellm-rust
- Pin: `76f83257fce4dcc3d76e7e760934bbd725b624d9`
- Role: Rust LLM gateway prototype
- Mode: `SANDBOX_ONLY`
- Integration: reference only pending benchmark and security review.

### langchain-ai/langchain-litellm
- Pin: `5b8af479f783ae5a0d3eff9214c2cbb06473e513`
- Role: LangChain provider adapter
- Mode: `SANDBOX_ONLY`
- Integration: adapter reference pending compatibility and transitive dependency review.



## Security gate update — checked 2026-10-09

LiteLLM is **not approved for production installation** by this federation sync. Review the upstream advisories before any runtime decision:

- [GHSA-7hp6-4w63-5g45 — critical proxy-admin privilege escalation](https://github.com/BerriAI/litellm/security/advisories/GHSA-7hp6-4w63-5g45). The advisory lists patched branches including 1.100.4, 1.101.3, 1.102.2, and 1.103.1; confirm the exact release actually deployed.
- [GHSA-g5ff-637f-6q2m — high-severity local file read via `vertex_ai_credentials`](https://github.com/BerriAI/litellm/security/advisories/GHSA-g5ff-637f-6q2m). The advisory lists 1.95.0 as patched.
- [GHSA-3cv6-jpf6-8222 — authenticated SSRF and provider-credential exfiltration](https://github.com/BerriAI/litellm/security/advisories/GHSA-3cv6-jpf6-8222). Patched releases vary by branch; the advisory lists fixes including 1.96.2, 1.95.1, 1.94.3, 1.93.2, 1.92.2, 1.91.5, 1.90.7, 1.89.7, and 1.88.6.

A Git commit pin alone does not prove which released package, container image, or dependency set will run. Before testing a gateway outside an isolated development environment, verify its exact version and image signature, apply the applicable fixes, disable client-supplied credential overrides, enforce upstream host validation, restrict network egress, and keep all Deriv and production-host secrets out of the gateway. Do not expose the gateway's management API to untrusted networks.



## Freebuff / Codebuff proxy source review — 2026-10-09

The following 19 repositories have been pinned for reference or isolated development review only. **None is installed or approved as an AURELIA runtime dependency.** The source labels and exact default-branch pins are in `config/external_repo_federation.json`; agent assignments and install status are in `config/agent_capability_matrix.json`.

| Repository | Pin | License metadata | Mode | Primary agent |
|---|---|---|---|---|
| `jxjhheric/freebuff2api-wokers` | `5cbb353019f2…` | MIT | REFERENCE_ONLY | GoogleAgentSkills |
| `kele68108/Freebuff2API-Optimized` | `f7e13d414e9a…` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills |
| `t479842598/freebuff2api-vercel` | `16274ad8f3b9…` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills |
| `HengXin666/freebuff-proxy` | `581097b0b7ba…` | MIT | REFERENCE_ONLY | GoogleAgentSkills |
| `lza6/Freebuff-2API` | `bd607aac7054…` | MIT | REFERENCE_ONLY | GoogleAgentSkills |
| `NetroIndonesia/freebuff2api` | `4894d7db6157…` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills |
| `XxxXTeam/freebuff2api` | `0c691c7dc90b…` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills |
| `Quorinex/Freebuff2API` | `a1c10357098f…` | MIT | REFERENCE_ONLY | GoogleAgentSkills |
| `pingmike2/freebuff2api-wokers` | `901a9d87c748…` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills |
| `CodebuffAI/freebuff` | `18f32cd3c51e…` | Apache-2.0 | REFERENCE_ONLY | ClaudeCode |
| `VenTheZone/freebuff-gate` | `3663a93614f0…` | NOASSERTION | SANDBOX_ONLY | PlaywrightCLI |
| `Praket7/freebuff-mcp` | `02cf6e623cc6…` | NOASSERTION | SANDBOX_ONLY | GoogleAgentSkills |
| `Jakevin/codex-freebuff-web` | `576c6835bc06…` | MIT | SANDBOX_ONLY | ClaudeCode |
| `TheMetalStorm/herdr-freebuff-plugin` | `a49b1ea428fe…` | MIT | REFERENCE_ONLY | GrokBot |
| `Heartcoolman/FreeBuff` | `9edc400ca83c…` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills |
| `HaizhuAI/Freebuff2apic` | `58ff9bdbbc74…` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills |
| `0xgetz/freebuff-9router` | `ec5e698816d8…` | MIT | REFERENCE_ONLY | GoogleAgentSkills |
| `aminkalantari842-ui/global-intelligence-os` | `05ea36d535e2…` | NOASSERTION | REFERENCE_ONLY | GrokBot |
| `6yte96/freebuffet` | `280259f0495f…` | MIT | SANDBOX_ONLY | ClaudeCode |

### Restrictions and findings

- The official `CodebuffAI/freebuff` repository is the upstream coding-agent reference. The other API bridges and proxy forks may reimplement the client protocol, manage account pools/tokens, or randomize request fingerprints. This audit records those traits only to define a security boundary; it does not implement them.
- `NetroIndonesia/freebuff2api` explicitly warns in its README about Freebuff/Codebuff Terms-of-Service risk and account restrictions. `pingmike2/freebuff2api-wokers` warns that Cloudflare Worker deployment may increase account-ban risk. See the original READMEs: [NetroIndonesia/freebuff2api](https://github.com/NetroIndonesia/freebuff2api) and [pingmike2/freebuff2api-wokers](https://github.com/pingmike2/freebuff2api-wokers).
- Do not deploy or use these sources to evade usage limits, account restrictions, bans, access controls, session policy, or provider terms. Do not use randomised fingerprints, account-pool rotation, or reverse-engineered protocol flows to circumvent the upstream controls.
- Do not submit Deriv tokens, account IDs, broker messages, production SSH keys, or any AURELIA production secret to Freebuff, a third-party proxy, a model gateway, an MCP server, or vector memory. Keep untrusted agents in isolated dev profiles with only disposable development context and explicit approval before any local file write/tool invocation.
- `Praket7/freebuff-mcp` can call the local Freebuff application and read project files. Its own README notes that secret-pattern masking can miss unusual secrets; masking is not a complete security boundary. Use it only in a disposable sandbox and do not connect it to the production trading repository with secrets present.
- `global-intelligence-os` and several proxy repositories have no declared license in GitHub API metadata. They remain reference-only until license and ownership are clarified.

This is repository federation and source pinning—not physical installation, credential transfer, an authenticated provider connection, or proof that ChatGPT/Claude/Dev runtimes are connected. The label `Dev` is not a canonical agent identity in this repository; developer-oriented work is routed to `ClaudeCode` unless a real Dev runtime is registered and verified.


## Pine Script, TradingView, and Pinecone source batch — 2026-10-09

Twenty requested repositories are registered with exact default-branch commit pins, agent assignments, and a mode that does not grant capital authority. They are not installed into AURELIA's production runtime.

| Repository | Pin | License metadata | Mode | Review note |
|---|---|---|---|---|
| [pineforge-4pass/pineforge-engine](https://github.com/pineforge-4pass/pineforge-engine) | `873b25daa00687cd2b9b9d6b2e49c57149227edd` | Apache-2.0 | RESEARCH_ONLY | Pine Script v6 code generation/backtesting engine; validate semantics, broker execution differences and OOS results. |
| [pinecone-io/pinecone-claude-code-plugin](https://github.com/pinecone-io/pinecone-claude-code-plugin) | `c383d38b5cc3c5ec219f2e68026e47ffbf46524a` | MIT | TOOLCHAIN_ONLY | Official Pinecone Claude Code marketplace plugin; vector search integration only. |
| [tmustier/pine-of-glass](https://github.com/tmustier/pine-of-glass) | `6e7dd5fd613198fee9fff71df1bc45a579030cce` | MIT | REFERENCE_ONLY | Pi coding-agent observability/context extension; do not assume Claude runtime compatibility. |
| [FaustoS88/Pydantic-AI-Pinescript-Expert](https://github.com/FaustoS88/Pydantic-AI-Pinescript-Expert) | `03cbd93c486435df08d70185fbab9aa61fff5fbb` | MIT | RESEARCH_ONLY | Pine Script RAG/code-generation assistant; generated signals remain unqualified until independent testing. |
| [be-thomas/OpenPineScript](https://github.com/be-thomas/OpenPineScript) | `a793e719043a0a05dc7c184b04ef4ad6985d0de9` | GPL-3.0 | RESEARCH_ONLY | Pine Script runtime; GPL-3.0 compatibility and semantic completeness review required. |
| [jpantsjoha/pinescript-vscode-extension](https://github.com/jpantsjoha/pinescript-vscode-extension) | `b81aa3d88f6327328ebf84b851757bd6266e56f8` | NOASSERTION | TOOLCHAIN_ONLY | Pine Script v6 editor extension; license must be clarified before redistribution. |
| [double232/pinescript-skill](https://github.com/double232/pinescript-skill) | `107fd4c6f4abd6cf64639040d6d67b42d130aa3d` | NOASSERTION | REFERENCE_ONLY | Pine Script v6 skill reference; inspect prompts/dependencies; license not declared. |
| [gugu91/pinet](https://github.com/gugu91/pinet) | `78b24b7ce6abd3e7cb793b31a399041c7d6a3c7a` | MIT | TOOLCHAIN_ONLY | Local-first coordination for Pi coding agents; no production credentials. |
| [folknor/pine-tools](https://github.com/folknor/pine-tools) | `3dd9f3c941ece3368e500360dd9e6e125ad396f6` | NOASSERTION | TOOLCHAIN_ONLY | Pine language service/LSP/MCP/CLI linting; license review before adoption. |
| [dharmanan/PineScript-coder](https://github.com/dharmanan/PineScript-coder) | `5f4c0f65e58b60860a920c2c59670ed21b1a9eaa` | MIT | RESEARCH_ONLY | Pine Script v6 generation; test repaint/lookahead, fees and fill semantics. |
| [dotsystemsdevs/pineflow](https://github.com/dotsystemsdevs/pineflow) | `8d2dbbc2a5b3061d102c6beb2e9070c4c4f05e3d` | MIT | REFERENCE_ONLY | AI coding prompts/workflow toolkit; not a Pine-specific trading runtime. |
| [batonogov/pine](https://github.com/batonogov/pine) | `c5ed7a4c4744c4dfd4ff88dd20cc94a2c81b96d1` | MIT | TOOLCHAIN_ONLY | Native macOS agent editor; not available in current runtime unless separately installed. |
| [edeng23/pines](https://github.com/edeng23/pines) | `c6020543236360c92adff8ee48d621b1d4b3759f` | Apache-2.0 | TOOLCHAIN_ONLY | Pi multi-session orchestration TUI; no proof Pi runtime is connected. |
| [TheFractalyst/PineMCP](https://github.com/TheFractalyst/PineMCP) | `c630de784c795d8abc5e15780881f5237dba8bdc` | MIT | SANDBOX_ONLY | Local Pine Script docs/code MCP; isolate and review tool permissions before activation. |
| [85599/pinesprout](https://github.com/85599/pinesprout) | `48bcea15275351869dffa1a3ba5fa6ffebd1f983` | MIT | RESEARCH_ONLY | Pine Script v5/v6 lint/format/upgrade toolkit; use as analysis only until validated. |
| [hasnocool/tradingview-script-downloader](https://github.com/hasnocool/tradingview-script-downloader) | `997d5417235c4fa9d4e20d56b02fe6b0fd3fd37d` | NOASSERTION | REFERENCE_ONLY | Selenium/BeautifulSoup public script downloader; no unlicensed code reuse or logged-in session scraping. |
| [coocolab/Coocolab-Tradingview-MCP](https://github.com/coocolab/Coocolab-Tradingview-MCP) | `cd16a7dc038762688e7807a26285a26337d6fc60` | NOASSERTION | SANDBOX_ONLY | Desktop TradingView MCP; never attach production browser session or broker secrets. |
| [daviddme/tradingview-indicator-search-mcp-server](https://github.com/daviddme/tradingview-indicator-search-mcp-server) | `1f8648936088cf189e4ac1a23b55c522c11d15cd` | MIT | SANDBOX_ONLY | Public indicator search/source fetch MCP; respect author licenses and platform access controls. |
| [kashsuks/Pinel](https://github.com/kashsuks/Pinel) | `1b10a5f8c8f772a27360d77dae33be5137bc7a66` | GPL-3.0 | TOOLCHAIN_ONLY | Rust code editor; GPL-3.0 compatibility review and separate installation required. |
| [pinecone-io/getting-started-with-pinecone-webinar](https://github.com/pinecone-io/getting-started-with-pinecone-webinar) | `76068a1b11a5c33dd82192f31ba5377c46c656cf` | MIT | REFERENCE_ONLY | Pinecone educational examples; docs/demo only, not production dependencies. |

### Integration rules
- Pine Script generators, runtimes, and backtest engines are research-only until indicator semantics, repaint/lookahead behavior, execution timing, costs, and out-of-sample results are independently validated.
- GPL-3.0 sources require a compatibility review before redistribution or linking into proprietary components. Sources without declared license metadata remain unapproved for redistribution.
- TradingView MCP/browser automation is isolated sandbox tooling. Do not mount authenticated TradingView or Deriv sessions, browser cookies, production credentials, or SSH keys into external MCP servers.
- Public script discovery is not permission to copy/reuse source code without respecting author licenses and platform rules.
- Pinecone examples/plugins do not prove a connected Pinecone account, API key, or live Claude runtime. No credentials are embedded by this registry change.
- All new skill records set `capital_authority: false`. AURELIA's deterministic risk/execution controls remain the sole capital authority.
