# AURELIA — Freebuff and Freebuff-adjacent repository review

Date checked: 2026-10-09  
Status: **19 repositories pinned; no production installation performed**.

## Decision

All listed repositories are in AURELIA's source registry and assigned to canonical engineering/security/research agents. Nine proxy-related sources are `REFERENCE_ONLY`, and the remaining sources are either `REFERENCE_ONLY` or `SANDBOX_ONLY`. None is installed in the production trading runtime.

These projects may inform coding-agent integration research, but their existence does **not** provision GitHub environment secrets, authenticate a Deriv session, deploy a persistent worker, qualify a strategy, or grant AURELIA capital authority. We do not use a free-provider proxy as a workaround for missing Deriv authentication.

## Exact source pins and review assignment

| Repository | Default-branch commit pin | GitHub license metadata | Mode | Primary reviewer | Notes |
|---|---|---|---|---|---|
| [jxjhheric/freebuff2api-wokers](https://github.com/jxjhheric/freebuff2api-wokers) | `5cbb353019f2f660ca1d72984549e430590b4778` | MIT | REFERENCE_ONLY | GoogleAgentSkills | Cloudflare Worker OpenAI-compatible proxy; source reference only. |
| [kele68108/Freebuff2API-Optimized](https://github.com/kele68108/Freebuff2API-Optimized) | `f7e13d414e9a7197a227969d88ad6166724c2a15` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills | Optimized proxy fork; multi-account/session reuse behavior needs legal/security review. |
| [t479842598/freebuff2api-vercel](https://github.com/t479842598/freebuff2api-vercel) | `16274ad8f3b9fa9c30093ab859f3732aca043452` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills | Vercel deployment adapter; secret storage, auth, logging and request-handling review only. |
| [HengXin666/freebuff-proxy](https://github.com/HengXin666/freebuff-proxy) | `581097b0b7ba14a57fca487936975d97474d9bb8` | MIT | REFERENCE_ONLY | GoogleAgentSkills | Reverse-engineered protocol and account pool; not deployed. |
| [lza6/Freebuff-2API](https://github.com/lza6/Freebuff-2API) | `bd607aac70548b80f586c60f819ed8e47240e25f` | MIT | REFERENCE_ONLY | GoogleAgentSkills | Rust proxy with token/cookie ingestion and account pool; not deployed. |
| [NetroIndonesia/freebuff2api](https://github.com/NetroIndonesia/freebuff2api) | `4894d7db6157c97f3037dc7d79ae0c2571762f8e` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills | Project explicitly documents ToS risk and risk of account restrictions. |
| [XxxXTeam/freebuff2api](https://github.com/XxxXTeam/freebuff2api) | `0c691c7dc90b91589e53901ea39dee96b28bf157` | AGPL-3.0 | REFERENCE_ONLY | GoogleAgentSkills | API adapter reference; no copied tokens or production deployment. |
| [Quorinex/Freebuff2API](https://github.com/Quorinex/Freebuff2API) | `a1c10357098f0615a8b605bf32ed9455e33320e4` | MIT | REFERENCE_ONLY | GoogleAgentSkills | Dynamic request fingerprints and token rotation; no evasion or deployment. |
| [pingmike2/freebuff2api-wokers](https://github.com/pingmike2/freebuff2api-wokers) | `901a9d87c748072fea16c8cc4d5e9d3bca87d593` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills | Cloudflare Worker proxy fork; upstream README warns edge deployment can increase ban risk. |
| [CodebuffAI/freebuff](https://github.com/CodebuffAI/freebuff) | `18f32cd3c51ea88d763e89432642a908030fd088` | Apache-2.0 | REFERENCE_ONLY | ClaudeCode | Official Freebuff CLI/product source reference. |
| [VenTheZone/freebuff-gate](https://github.com/VenTheZone/freebuff-gate) | `3663a93614f0abbfcb477563538014e1f35b0cd4` | NOASSERTION | SANDBOX_ONLY | PlaywrightCLI | Desktop UI/relay; use only local isolated profile, no public exposure. |
| [Praket7/freebuff-mcp](https://github.com/Praket7/freebuff-mcp) | `02cf6e623cc6643fba3aeadeba3011188857212d` | NOASSERTION | SANDBOX_ONLY | GoogleAgentSkills | MCP bridge can issue local coding-agent requests and read project files; manual approval and sandbox only. |
| [Jakevin/codex-freebuff-web](https://github.com/Jakevin/codex-freebuff-web) | `576c6835bc06ed4fc039bb6cd264e73ce36efa41` | MIT | SANDBOX_ONLY | ClaudeCode | Codex bridge for official sessions; developer sandbox only. |
| [TheMetalStorm/herdr-freebuff-plugin](https://github.com/TheMetalStorm/herdr-freebuff-plugin) | `a49b1ea428fe6eb620288a3035984073927557d2` | MIT | REFERENCE_ONLY | GrokBot | Plugin polls files and scrapes PTY content to infer state; privacy review only. |
| [Heartcoolman/FreeBuff](https://github.com/Heartcoolman/FreeBuff) | `9edc400ca83c347554dba8fb373e63af8fcfbcd2` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills | Local OpenAI/Anthropic-compatible bridge; not deployed. |
| [HaizhuAI/Freebuff2apic](https://github.com/HaizhuAI/Freebuff2apic) | `58ff9bdbbc749b8a607a2960ee89d6f29927ca0f` | NOASSERTION | REFERENCE_ONLY | GoogleAgentSkills | Account-pool and proxy-routing gateway reference. |
| [0xgetz/freebuff-9router](https://github.com/0xgetz/freebuff-9router) | `ec5e698816d86b4db1d970e03d10350bcc15d966` | MIT | REFERENCE_ONLY | GoogleAgentSkills | Freebuff/9router gateway adapter; review auth and secret boundaries only. |
| [aminkalantari842-ui/global-intelligence-os](https://github.com/aminkalantari842-ui/global-intelligence-os) | `05ea36d535e2076a359b7fdeb82d99e77f66ae4e` | NOASSERTION | REFERENCE_ONLY | GrokBot | Broad agent-intelligence project with no license declared in repository metadata; inspect before use. |
| [6yte96/freebuffet](https://github.com/6yte96/freebuffet) | `280259f0495f8d37b7cd51a19500e8eb0eab8223` | MIT | SANDBOX_ONLY | ClaudeCode | Provider config-generation CLI; never write its output into production hosts without review. |

## Findings affecting admission

1. Several proxy forks reimplement the upstream Freebuff/Codebuff client protocol or manage tokens, sessions, or account pools. Some describe randomized request fingerprints or multi-account routing. These are not approved for quota circumvention, ban evasion, session-policy bypass, or other attempts to defeat provider access controls.
2. The [NetroIndonesia project README](https://github.com/NetroIndonesia/freebuff2api) explicitly warns that use conflicts with upstream Terms of Service and can result in rate limits or account bans. The [pingmike2 Worker fork README](https://github.com/pingmike2/freebuff2api-wokers) warns that Cloudflare deployment may increase account-ban risk. These are reasons for reference-only status, not deployment instructions.
3. The [Freebuff MCP README](https://github.com/Praket7/freebuff-mcp) describes requests sent to a local Freebuff app and access to ordinary project files. Its secret-pattern masking is not a complete security boundary. Only test in a disposable, non-production checkout with explicit review of each tool/write permission.
4. The [Freebuff Gate README](https://github.com/VenTheZone/freebuff-gate) describes a local UI/relay and gate token. It is not to be exposed on public interfaces or used with a logged-in production trading session.
5. [FreeBuffet](https://github.com/6yte96/freebuffet) can generate provider configurations and prompts for API keys. Inspect generated files before use; no tool may automatically apply them to AURELIA's production host.
6. GitHub's API metadata returns no declared license for several sources. Those stay reference-only until licensing and ownership are established.

## Secret and capital-plane boundary

Never send any of the following to these third-party projects: Deriv tokens, authorized Deriv account IDs, account credentials, broker messages, production SSH keys, GitHub write tokens, or secrets from `/etc/aurelia/aurelia.env`. Do not mount the production AURELIA checkout or production secret store into an MCP bridge, proxy container, free model router, vector database, or modified coding-agent runtime.

The existing AURELIA controls remain canonical: Balance Truth, Account Isolation, Risk Warden, Execution Firewall, idempotency, transaction verification, ledger reconciliation, independent kill switch and `config/LIVE_LOCK.yaml`. External repositories cannot change the lock, authorize orders, or read production secrets.

## Synchronization semantics

The full pins are recorded in `config/external_repo_federation.json` and `config/agent_skill_federation.json`, with assignment metadata in `config/agent_capability_matrix.json`. This preserves provenance and makes the sources available for ChatGPT's in-session review and for repository-connected Claude Code work. It does not install them into the current ChatGPT product, connect an unverified Claude runtime, or prove a separate Dev runtime exists. In AURELIA's current agent roster, developer implementation tasks route to `ClaudeCode`; “Dev” is not a separate verified identity.

## Security references

- [Freebuff/Codebuff public proxy README and Terms-of-Service caveat](https://github.com/NetroIndonesia/freebuff2api)
- [Cloudflare Worker deployment risk noted upstream](https://github.com/pingmike2/freebuff2api-wokers)
- [Local MCP bridge behavior and limitations](https://github.com/Praket7/freebuff-mcp)
- [Local gate/relay architecture](https://github.com/VenTheZone/freebuff-gate)
