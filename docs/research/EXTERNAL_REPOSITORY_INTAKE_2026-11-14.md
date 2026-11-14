# External Repository Intake — 14 November 2026

## Decision

**Disposition: registered as pinned, non-authoritative references; no executable repository was installed or run.**

This intake covers all 26 repositories supplied for AURELIA and Claude Code. The upstream default-branch commit for each source was resolved through GitHub and recorded below. Pins improve reproducibility; they do not establish trust, safety, compatibility, or profitability.

The canonical policy remains unchanged: external code execution is `DENY_BY_DEFAULT`; external sources have no capital authority, no production-secret access, no live-order authority, and no production-deployment authority. No source was copied into `capital/`, `execution/`, or broker/runtime paths. No MCP server, hook, LSP, agent, workflow, package, or trading dependency was enabled.

A Desktop Commander check returned **no connected devices**. Therefore this change can synchronize the AURELIA GitHub repository and its project-level Claude instructions only. It cannot install software into a local Claude Code desktop/runtime.

## High-risk exclusions

- **EternaHybridExchange/mcp-trading-agent — DO NOT INSTALL OR ENABLE.** Its README advertises `place_order`, `close_position`, and `transfer_to_trading`; the Claude Code setup points to a hosted MCP gateway and instructs users to register an agent and place trades. Its sample MCP config is intentionally not copied into AURELIA's `.mcp.json`. This crosses the current no-external-capital-authority boundary.
- **four-meme-community/four-meme-ai — reference only.** It is a CLI for creating and trading meme tokens on BSC. No wallet, key, or transaction capability is introduced.
- **jamesmawm/High-Frequency-Trading-Model-with-IB — research only, not reusable as runtime.** The repository documents Python 3.7-era dependencies and an Interactive Brokers TWS trading loop; its own README says it was never used with a real account and its strategies are not proven profitable.
- **zadescoxp/calibrain-harness — research only.** It is explicitly under development and Bybit-testnet-only. Its own reported early runs total approximately -2,601 USDT over one day/one market regime; its metrics and independent-window validation approach may be studied, but its Bybit execution code is not a Deriv/AURELIA adapter.
- **can1357/oh-my-pi — reference only.** This is a full coding-agent runtime with shell/code tools, LSP/DAP, subagents, and external provider integrations, not a Claude Code skill. No installer or runtime was invoked.
- **ChrisWiles/claude-code-showcase — reference only.** It includes hooks, MCP examples, auto-approval examples, and GitHub Actions. No hook, MCP configuration, auto-approval, or workflow was copied; license metadata was not verified in this intake.
- **LenWilliamson/chapaty-template — research only.** It is a separate Rust quant/backtesting stack. Its `make update` fetches upstream files over the network, overwrites prompt/visualization/Makefile files, and runs `cargo update`; no setup/update command was run.

## Source register

All SHAs are the resolved default-branch HEADs checked on 2026-11-14.

| Repository | Pinned commit | Mode | Intake note |
|---|---|---|---|
| [`jamesmawm/High-Frequency-Trading-Model-with-IB`](https://github.com/jamesmawm/High-Frequency-Trading-Model-with-IB) | `8e96ade54a8e` | `RESEARCH_ONLY` | Legacy IB example; not proven live-profitable; incompatible runtime |
| [`zadescoxp/calibrain-harness`](https://github.com/zadescoxp/calibrain-harness) | `d9a3a62d1e64` | `RESEARCH_ONLY` | Bybit testnet research; inspect metrics only, never attach its broker |
| [`calibrain/calibrain`](https://github.com/calibrain/calibrain) | `1f7ec11c5984` | `REFERENCE_ONLY` | GitHub profile configuration repository |
| [`can1357/oh-my-pi`](https://github.com/can1357/oh-my-pi) | `af8e4c142b2b` | `REFERENCE_ONLY` | Separate coding-agent runtime; no install |
| [`four-meme-community/four-meme-ai`](https://github.com/four-meme-community/four-meme-ai) | `0a07b65468ca` | `REFERENCE_ONLY` | BSC meme-token creation/trading CLI; no wallet use |
| [`Artillex-Studios/AxTrade`](https://github.com/Artillex-Studios/AxTrade) | `99260b7de23a` | `REFERENCE_ONLY` | Minecraft trade plugin; unrelated to financial trading |
| [`EternaHybridExchange/mcp-trading-agent`](https://github.com/EternaHybridExchange/mcp-trading-agent) | `c048e928e668` | `REFERENCE_ONLY` | Capital-capable MCP; blocked from install/config |
| [`LenWilliamson/chapaty-template`](https://github.com/LenWilliamson/chapaty-template) | `065238a44a7e` | `RESEARCH_ONLY` | Independent Rust research/backtesting template; no code sync |
| [`lneufinck67/Trading-Automation-Experience`](https://github.com/lneufinck67/Trading-Automation-Experience) | `1f9fe99a745d` | `REFERENCE_ONLY` | README-only experience profile; no implementation to install |
| [`kubernetes/org`](https://github.com/kubernetes/org) | `d863f450590f` | `REFERENCE_ONLY` | Kubernetes GitHub organization metadata |
| [`github/awesome-copilot`](https://github.com/github/awesome-copilot) | `8ecd5b17f02f` | `REFERENCE_ONLY` | Community Copilot agent/skill catalog; individual items require review |
| [`jenkinsci/.github`](https://github.com/jenkinsci/.github) | `bfd0c12af711` | `REFERENCE_ONLY` | Jenkins organization-wide GitHub defaults |
| [`editorconfig/editorconfig.github.com`](https://github.com/editorconfig/editorconfig.github.com) | `fb12e8af5d81` | `REFERENCE_ONLY` | EditorConfig website/content |
| [`eBUS/ebus.github.io`](https://github.com/eBUS/ebus.github.io) | `8f6e45a67c9e` | `REFERENCE_ONLY` | eBUS configuration files |
| [`ChrisWiles/claude-code-showcase`](https://github.com/ChrisWiles/claude-code-showcase) | `a95518f0cb67` | `REFERENCE_ONLY` | Claude examples; executable hooks and MCP configs excluded |
| [`shivammathur/setup-php`](https://github.com/shivammathur/setup-php) | `9a96576163ad` | `REFERENCE_ONLY` | PHP GitHub Action; not relevant to AURELIA Python runtime |
| [`dolmen/github-keygen`](https://github.com/dolmen/github-keygen) | `37e312549a9a` | `REFERENCE_ONLY` | SSH key/config utility; no SSH config mutation |
| [`debezium/debezium-examples`](https://github.com/debezium/debezium-examples) | `c90f5448e426` | `REFERENCE_ONLY` | CDC examples; no current integration target |
| [`keploy/.github`](https://github.com/keploy/.github) | `ec3b0b7f536a` | `REFERENCE_ONLY` | Keploy organization profile config |
| [`paketo-buildpacks/github-config`](https://github.com/paketo-buildpacks/github-config) | `5779d4b1778b` | `REFERENCE_ONLY` | Shared GitHub configuration |
| [`bahmutov/npm-install`](https://github.com/bahmutov/npm-install) | `20216767ca67` | `REFERENCE_ONLY` | npm install GitHub Action; not relevant to Python runtime |
| [`w3c/github-notify-ml-config`](https://github.com/w3c/github-notify-ml-config) | `024f6cd80058` | `REFERENCE_ONLY` | W3C mailing-list notification config |
| [`affaan-m/agentshield`](https://github.com/affaan-m/agentshield) | `b0891303bdcd` | `SANDBOX_ONLY` | Already registered; candidate for an isolated config scan after independent validation |
| [`bytebase/clabot-config`](https://github.com/bytebase/clabot-config) | `f2d63ed39b29` | `REFERENCE_ONLY` | CLA bot config |
| [`ipdxco/github-as-code`](https://github.com/ipdxco/github-as-code) | `eaa899daff93` | `REFERENCE_ONLY` | GitHub configuration-as-code; no org mutation authorized |
| [`renovatebot/.github`](https://github.com/renovatebot/.github) | `3f317d18df3a` | `REFERENCE_ONLY` | Renovate shared config; reference only pending CI/permission review |

## AURELIA and Claude Code synchronization

- `config/external_repo_federation.json` gains 25 new pinned entries. `affaan-m/agentshield` was already registered and remains `SANDBOX_ONLY`; its pin was rechecked.
- `.claude/skills/aurelia-federated-repair/SKILL.md` now requires Claude Code to read this intake report and the canonical federation registry before using a candidate source.
- `CLAUDE.md` explicitly states this is a reference register, not installation approval, and forbids importing trading MCPs/hooks or external code into capital/execution paths.
- `config/LIVE_LOCK.yaml`, `AURELIA_SOURCE_OF_TRUTH.json`, broker adapters, execution code, dependency manifests, and `.mcp.json` are not modified.

## Validation and remaining gate

This is a preliminary repository triage, not a full line-by-line security audit of all 26 repositories. Full review is still required before any source is promoted beyond its registered mode. The exact pinned commits, repo descriptions, and selected manifests/README files were inspected for the high-risk entries. No source was executed; no package installation, credential retrieval, API-key registration, wallet interaction, trading action, or deployment occurred.

After this draft PR is reviewed, it may be merged as a documentation/registry-only change. Physical Claude Code installation remains unavailable until an authorized device is connected and its runtime identity/configuration is verified.
