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

## TradingAgents multi-agent research federation — checked 2026-11-05

Four requested repositories are pinned as research sources, not installed runtime dependencies. Integration owner: ClaudeCode; quantitative review: KimiK3; adversarial orchestration review: GrokBot; evidence/schema review: JEV. All assignments are non-capital and require independently verified worker runtimes before task execution.

| Repository | Full commit pin | License | Mode | Status |
|---|---|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | `9fa1196fffbcfd9de5146d2dd2869df84ab99838` | Apache-2.0 | RESEARCH_ONLY | PINNED_REFERENCE_ONLY |
| [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) | `51060a7682cf51810b4bc3a704829438d18cd8dc` | Hybrid: Apache-2.0 scoped paths + proprietary app/frontend/core | RESEARCH_ONLY | PINNED_REFERENCE_ONLY |
| [simonlin1212/TradingAgents-astock](https://github.com/simonlin1212/TradingAgents-astock) | `3a9171182304e87042743dde245c64922e04ed96` | Apache-2.0 | RESEARCH_ONLY | PINNED_REFERENCE_ONLY |
| [KylinMountain/TradingAgents-AShare](https://github.com/KylinMountain/TradingAgents-AShare) | `63b25eda444377366ab6e4e265228454c51713f3` | Apache-2.0 upstream portions + PolyForm Noncommercial additions/modifications | RESEARCH_ONLY | PINNED_REFERENCE_ONLY |

### Integration boundary

- Use the original TauricResearch project as the primary workflow reference; forks are specialized references, not independent corroborating alpha sources.
- Do not copy TradingAgents-CN proprietary application directories or KylinMountain PolyForm Noncommercial additions into a commercial AURELIA deployment without permission.
- Do not add any of these projects' dependency trees to the AURELIA runtime. If needed, run an isolated research adapter with a separately pinned environment and communicate only over the existing worker JSONL protocol.
- ClaudeCode owns the adapter/research integration; KimiK3, GrokBot and JEV provide independent non-capital review when their real runtimes are available.
- No worker may promote a strategy, alter risk, access broker credentials, or submit orders. All outputs are advisory evidence for Layer 9 and require canonical qualification.
- The A-share-only sources are not directly applicable to Deriv synthetic indices; do not import T+1, price-limit, hot-money or A-share vendor assumptions into synthetic research.

Detailed contract: `docs/integrations/TRADINGAGENTS_RESEARCH_FEDERATION.md`. Machine-readable pins and license restrictions: `config/external_repo_federation.json`.


## Metadata, provenance and tooling sources — 2026-11-05

The following 19 repositories are pinned at exact upstream default-branch commits. These are federated references, not blanket runtime installations. All entries have `runtime_dependency=false`, `runtime_install=NOT_INSTALLED`, and `capital_authority=false`.

| Repository | Pinned commit | License | Mode | AURELIA disposition |
|---|---|---|---|---|
| [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) | `96e4d8eb5ba1212d2d6018f242de266284cffab9` | MIT | SANDBOX_ONLY | High-privilege agent harness with shell, persistent execution, browser and desktop control. Reference only until independently isolated and permission-audited; never replace AURELIA's supervisor or worker boundary. |
| [ethereum-lists/chains](https://github.com/ethereum-lists/chains) | `e17474286275730fb6b0490b1d7ea1c64a36ed9e` | MIT | REFERENCE_ONLY | Only for future EVM integrations. Does not describe Deriv synthetic indices or provide broker instrument metadata. |
| [open-metadata/OpenMetadata](https://github.com/open-metadata/OpenMetadata) | `a3012259ca604141e3f778aa3f259d827371470a` | Apache-2.0 | REFERENCE_ONLY | Architecture reference for evidence cataloguing and governed data context. Do not deploy a new service or add its dependency tree without a separate cost/security/ops decision. |
| [drewnoakes/metadata-extractor](https://github.com/drewnoakes/metadata-extractor) | `4d5cd46935c1987d8b19bfb49f3a24eb1d832e53` | Apache-2.0 | REFERENCE_ONLY | Not relevant to current Python trading runtime; use only if media-file evidence ingestion becomes a real requirement. |
| [ronmamo/reflections](https://github.com/ronmamo/reflections) | `f5514b125c4f4b58e92beb0979a40ddce48d5be1` | WTFPL (GitHub SPDX metadata; LICENSE file not found in root) | REFERENCE_ONLY | Upstream README states the project is not actively maintained and last release was 2021. No runtime adoption; verify exact license text before copying. |
| [microsoft/reflect-metadata](https://github.com/microsoft/reflect-metadata) | `acdeee445509ea05c8fab270f73928f7bb2c50f1` | Apache-2.0 | REFERENCE_ONLY | Legacy TypeScript decorator compatibility only; not part of the AURELIA Python runtime. TC39 standard decorator metadata supersedes the proposal for new projects. |
| [apache/ossie](https://github.com/apache/ossie) | `172a3e566f2fc9c0a733ebbb470e97c33d2bd8b1` | Apache-2.0 (Apache incubating project) | REFERENCE_ONLY | Evaluate the specification for canonical metric and strategy semantics; no converter or runtime package adopted yet. |
| [grafeas/grafeas](https://github.com/grafeas/grafeas) | `4a8bf366a01f0e509b9118b9f8afd64f211e64c6` | Apache-2.0 | REFERENCE_ONLY | Use as a provenance/evidence model reference. Do not add a Grafeas server or make its records authoritative for AURELIA release approval. |
| [docker/metadata-action](https://github.com/docker/metadata-action) | `1ec73021df0717d8bef7700a897c064453280439` | Apache-2.0 | TOOLCHAIN_ONLY | CI-only candidate for immutable image labels and release tags; not an application runtime dependency. |
| [google/ml-metadata](https://github.com/google/ml-metadata) | `7efdb25a3390cd1547372792ece6390e5b4364d1` | Apache-2.0 | REFERENCE_ONLY | Reference for experiment and model lineage. Existing AURELIA evidence store remains canonical; no MLMD service/database introduced. |
| [microsoft/win32metadata](https://github.com/microsoft/win32metadata) | `ae66c067ff3e9516fcc9cda09204bf72a9d57e56` | NOASSERTION; upstream Windows SDK header/artifact terms remain applicable | REFERENCE_ONLY | Windows-specific and irrelevant to current Linux/Python trading runtime. Repository LICENSE warns that original SDK header licenses are not changed; require provenance/legal review before reuse. |
| [drewnoakes/metadata-extractor-dotnet](https://github.com/drewnoakes/metadata-extractor-dotnet) | `cb71a8ad84a15dbf64ddb25a77c17cd855adfef4` | Apache-2.0 | REFERENCE_ONLY | Not relevant to current Python runtime; optional only for future .NET media evidence tooling. |
| [macbre/sql-metadata](https://github.com/macbre/sql-metadata) | `e48f1595cffaf409cef51fe1dfff21519da36ee5` | MIT | REFERENCE_ONLY | Use only if SQL lineage or audit query analysis becomes a requirement; parser metadata is not a substitute for database query plans or execution evidence. |
| [berachain/metadata](https://github.com/berachain/metadata) | `1cd819a51e50ec2d603f2409f382232c99ec1de0` | MIT | REFERENCE_ONLY | Chain-specific ecosystem list. Not a source of truth for Deriv instruments or general EVM chain configuration. |
| [Exiv2/exiv2](https://github.com/Exiv2/exiv2) | `ef4e79590c53cdef48bbed5629cdb81065b42287` | GPL-2.0-or-later (upstream LICENSE.txt SPDX identifier) | REFERENCE_ONLY | GPL licensing is incompatible with casual embedding in a proprietary AURELIA runtime absent a separate legal review or commercial licence. No installation. |
| [icsharpcode/ILSpy](https://github.com/icsharpcode/ILSpy) | `695f7aced9626eb5bffdf9a04a835cd984b9b5ce` | MIT | REFERENCE_ONLY | Forensic/developer utility only; do not use to bypass licensing, access controls or secrets. No AURELIA runtime dependency. |
| [jekyll/github-metadata](https://github.com/jekyll/github-metadata) | `c26a5d4574785fa79ecbccc1df890f3f9909a02d` | MIT | REFERENCE_ONLY | Website publishing plugin unrelated to AURELIA runtime; retained as a reference only. |
| [OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage) | `dd64b09365f08ee02a3a0653ddda0e62d8cc76f2` | Apache-2.0 | REFERENCE_ONLY | Strong candidate for mapping AURELIA research/validation runs to provenance events. Adopt concepts/schema selectively; no external lineage backend introduced. |
| [dependabot/fetch-metadata](https://github.com/dependabot/fetch-metadata) | `57721ba1e64f4a53fe9300b820eeee8398b772fb` | MIT | TOOLCHAIN_ONLY | CI-only candidate for dependency policy checks. Does not approve, merge or deploy dependency updates. |

### Selective adoption plan

- **Evidence lineage:** OpenLineage is the preferred event/schema reference for research, validation, test, soak and release evidence. Grafeas and ML Metadata are comparison references for artifact attestations and experiment tracking. Existing AURELIA evidence storage and release authority remain canonical.
- **Semantic governance:** Apache Ossie is a specification candidate for consistent metric, strategy and data-source definitions. OpenMetadata is an optional future catalog platform, not a service to deploy by default.
- **Agent harness:** oh-my-pi is a high-capability coding-agent reference only. Its shell, persistent execution, browser and desktop-control surfaces require independent OS sandboxing, command allowlists and secret isolation before any operational trial. It does not replace AURELIA's worker protocol or supervisor.
- **CI metadata:** Docker metadata-action and Dependabot fetch-metadata are workflow-only candidates. Any workflow adoption must be pinned by immutable commit, least-privilege, and review-gated; neither may auto-approve or auto-merge production changes.
- **Market metadata:** ethereum-lists/chains and Berachain metadata apply only to EVM chain integrations. They do not describe Deriv synthetic indices or broker contracts.
- **Non-applicable utilities:** Java/.NET reflection, TypeScript legacy decorator metadata, Win32 API metadata, ILSpy, media EXIF/IPTC/XMP extraction, Jekyll metadata and SQL parsing are reference-only until a specific AURELIA requirement exists.
- **License controls:** Exiv2's LICENSE.txt uses SPDX GPL-2.0-or-later; do not embed it in proprietary AURELIA without a licence decision. Win32 metadata's repository-authored code is MIT-licensed, but SDK-derived artifacts retain original Windows SDK terms; GitHub's API reports NOASSERTION for the repository. Reflections' repository reports WTFPL but has no root LICENSE file and is not actively maintained; verify before copying. Other listed license identifiers are recorded from GitHub metadata and/or root licence files; transitive dependency and vendored-code audits remain mandatory before installation.

### Agent and ChatGPT boundary

The `metadata-provenance` skill is assigned in the AURELIA capability matrix to all currently defined logical agents. The Claude Code skill file is included in this repository. This does not install packages on a local machine, activate an external provider, connect a worker, or modify the ChatGPT application. ChatGPT can use the repository evidence and skill guidance in a connected session; persistent ChatGPT-side installation is not exposed by GitHub.
