# Third-Party Repository Batch Triage — 2026-10-17

**Status: RESEARCH ONLY. No repository in this batch is approved for AURELIA production runtime.** This is an initial, source-grounded intake/triage, not a complete source audit, dependency vulnerability scan, build, or penetration test. Repository metadata was read from the GitHub API on 2026-10-17. Selected README/config files were inspected through GitHub's file API; where stated, their blob IDs are recorded below. The environment could not reliably clone upstream repositories, so no untrusted install/build scripts or WhatsApp pairing flows were run.

Canonical review: [PR #159](https://github.com/Anto-30/aurelia-trading/pull/159). Repository-protection blockers remain tracked in [Issue #160](https://github.com/Anto-30/aurelia-trading/issues/160).

## Required handling for this batch

- Do not add any of these repositories to AURELIA runtime, execution plane, Layer 6, broker adapters, or production agent tool registry.
- Do not pair any WhatsApp account, import a WhatsApp session, connect private chat history, deploy an externally reachable MCP server, or send test messages from a personal/business account as part of this review.
- Do not execute `curl | sh`, `curl | bash`, plugin installers, repo scripts, Docker Compose stacks, or package lifecycle scripts from unreviewed source.
- Do not expose broker credentials, WhatsApp session files, OAuth tokens, CRM data, customer PII, or environment files to any candidate agent.
- Any future development-time evaluation must use an isolated disposable environment, synthetic data, pinned immutable commit, verified license, lockfile-based dependency inventory, secret scan, SAST/dependency scan, network egress restrictions, and independent review.
- Third-party skills may supply read-only development guidance only after pinned review; no agent/skill gets authority to approve releases, alter risk limits, authorize capital, or send broker orders.
- Green CI and repository popularity are not security clearance.

## Highest-risk findings from the initial review

### WhatsApp bridges and agent channels

These projects can read private messages and/or send messages as a linked WhatsApp account. Incoming messages are untrusted content and can contain prompt injection. Persistent session credentials can grant account access. Keep all of these excluded from AURELIA until a separate threat model and isolated review is approved.

- **Rich627/whatsapp-claude-plugin** — README blob `61cf36b6f8ce9c45efd8b46d8e6cf0a0e47f49b3`; access policy blob `a125af31688dadc618e3c288c05311ac39148f53`. README documents the `--dangerously-load-development-channels` flag because inbound messages can wake a Claude session; it explicitly warns not to combine this with `--dangerously-skip-permissions`, and warns that the linked-device transport is unofficial. It offers a pairing/allowlist access gate and an official Cloud API option. **Disposition:** high risk; no install or account pairing. If ever evaluated, require official Cloud API where feasible, strict sender/group allowlists, interactive tool approvals, no unrestricted shell, and a disposable account.
- **ericporres/whatsapp-mcp-server** — README blob `da974be1df8ada0e714b1cfa71b5fe928b14cdc5`; package manifest blob `2d3682b63c18d8eab8b89e95755152f246d795f2`. README says Baileys linked-device protocol is used; auth/session files and message buffers persist locally. It documents OAuth 2.1/PKCE for remote HTTP clients, refusal to start with a public URL and no credentials, and a loopback-only unauthenticated test mode that must not be used behind a tunnel. Package manifest includes a Baileys 7 release-candidate range. **Disposition:** high risk; potential candidate only for isolated dev testing after pinning and dependency/protocol review. Never expose HTTP transport before OAuth is verified.
- **Sealjay/mcp-whatsapp** — README blob `e44da39ac986d873339c596bacc0d7f698825686`; Go manifest blob `2ab56aff37a98fd2781aa286189b490dfb6bb8bd`. README documents a local HTTP daemon defaulting to `127.0.0.1:8765`, a pairing UI, local SQLite message/session storage, a media-root restriction, and rejection of paths/symlinks outside that root. The tool surface includes messaging, group administration, media, and privacy settings. **Disposition:** high risk; local-only evaluation candidate after code review. Verify every remote-bind/authentication path, media handling, and all tools before any trial.
- **verygoodplugins/whatsapp-mcp** — README blob `b0109d022961d9232c0ee2eb16cdfb173cca6611`. README documents a generated bridge token, message-send/read tools, outbound webhook forwarding, media downloads, and a default HTTP host of `127.0.0.1`; it warns that remote binding exposes an account that can read and send messages. **Disposition:** high risk; require loopback-only operation, token protection, webhook destination allowlisting, data minimization, and a separate account before evaluation.
- **felipeadeildo/whatsapp-mcp** — README blob `b45dc61fa97a37cc6f69b868a5a0698348252463`. Cloudflare Workers/Durable Objects implementation with read/search/send capabilities; README states anyone with the configured `SECRET` can read and send messages and identifies the client as unofficial, with potential account-ban risk. **Disposition:** high risk; no personal account, no deployment, no message access. Review Cloudflare data boundaries and authentication before any isolated evaluation.
- **FelixIsaac/whatsapp-mcp-extended** — README blob `bd66ea6b4b515e595519b2351ee45f6a92ed252a`. README documents an API key, webhook signatures, an allowlist for outgoing messages, broad group/media/presence functionality, and warns that the linked-device bridge uses an unofficial API with account-ban risk. **Disposition:** high risk; static review only until API authentication, webhook replay handling, allowlist bypass resistance, and dependencies are tested.
- **ilanbenb/wa_llm** — README blob `cf21e16bd1c6115ef1f1e09a4f5f59051d79a034`. README lists `admin` as the example/default username and `admin` as the example/default password for the WhatsApp API, alongside production Docker Compose instructions. **Disposition:** block any deployment with defaults; require generated unique credentials, private-network binding, authentication tests, and a secrets review.
- **TitanmindAGI/titanmind-whatsapp-mcp** — README blob `0e6da21cd3cc3ee7c75b3b95277fa2d3046f2315`. Marketing/messaging MCP supports template workflows and bulk delivery; README includes remote MCP configuration and auth-key setup. Last repository push observed was 2025-07-16. **Disposition:** stale/high impact; do not connect a messaging credential or use bulk-send functions. Verify maintenance, official API compliance, consent controls, rate limits, and audit logging before reconsideration.
- **devlikeapro/waha** — README blob `e1ef401077647111a52abedcb07d17c0b5ae1fa4`. WhatsApp HTTP API with several transport engines and QR pairing; setup docs include shell-piped installers for prerequisites. **Disposition:** high risk; do not expose its API publicly or run installers without inspecting pinned scripts, authentication defaults, bind address, API-key handling, and container permissions. Prefer official WhatsApp Business Cloud API for compliant business messaging.
- **aldinokemal/go-whatsapp-web-multidevice** — Go WhatsApp REST API with UI, multiple accounts, webhooks, MCP and Chatwoot integration; license metadata was MIT. Source-level auth/network/container review not completed. **Disposition:** high risk; research only.
- **lgesuellip/langgraph-whatsapp-agent** — README blob `26b63bcda78f0646e15e655316bcea458c30babb`. Template uses Twilio webhooks and a LangGraph agent; README mentions request validation. **Disposition:** comparatively bounded integration candidate, but request validation alone is not sufficient. Verify Twilio signature checks, replay handling, tool permissions, PII retention, and model-injected tool calls before isolated testing.

### AI agent runtimes, plugins, and tool orchestration

- **EveryInc/compound-engineering-plugin** — README blob `7a86cef92094b644de4dffab69895ba233870e8b`; guide index blob `fed0a4a451266f8d57f56bd5fce916f9b6266f52`. Plugin bundles 36 engineering skills across agent hosts. The `lfg` workflow is documented as a hands-off pipeline that can implement, publish/push to a remote branch, and watch CI; merging remains user-controlled unless granted. **Disposition:** development-time prompt/skill assets only after pinning and static review; disable auto-push and remote side effects in AURELIA workspaces.
- **affaan-m/ECC** — README blob `6583ca8c1320e559aa5b2f86250f2f09c1d577e9`. README describes 71 agents, 311 skills, hooks, rules, memory and security scanning; install paths can write harness configuration and enable hooks. It says official sources only and cautions that a version pin is not an integrity check. **Disposition:** do not run full-profile installers or enable hooks. Review selected skills read-only at a pinned release, then test file changes in a disposable workspace.
- **ComposioHQ/composio** — README blob `96e883ce453757d4c2afec0c0bfc937c25cf24a2`. SDK/CLI provides 1000+ app toolkits, per-user sessions, authentication, triggers and action execution; README documents a shell-piped CLI installer. **Disposition:** not a default AURELIA dependency. Treat every connected toolkit as an external-action permission boundary; evaluate only a minimal allowlist with isolated credentials and explicit per-action approvals.
- **moltis-org/moltis** — README blob `bf72f8e6aa9eb026dccf82894b4e1e4efc2d29cc`. Agent server includes sandboxed tools, browser automation, MCP, messaging, SSH/remote execution and managed deploy keys; README install path pipes a remote script to a shell and a Docker example mounts the Docker socket. **Disposition:** high privilege; do not deploy on any host holding AURELIA secrets. A Docker socket mount can grant substantial host control; review threat model and sandbox escape boundary before any separate test.
- **trycompai/crm** — README blob `c761ebff650556235dd27f7c320ce94a6e5cdc30`. AI-first CRM runs scheduled autonomous research and follow-ups; README claims a sandbox with deny-all egress and no database access. It handles person/company identity evidence and customer records. **Disposition:** unrelated to trading execution; only evaluate for a separate CRM use case after verifying sandbox enforcement in code and testing data isolation, task scheduling, and PII deletion.
- **melgarafael/DeskcommCRM** — README blob `f05bf84a79fbe4ac5b8c13a4642b182be5a7250c`. Self-hosted AI sales CRM integrates WhatsApp/WAHA, Supabase, model-provider keys, Docker and a one-command install kit; docs offer a curl-piped setup helper but also describe cloning and reading the script first. **Disposition:** do not run the installer or provide keys. Requires a separately provisioned server and a complete review of install scripts, migrations, tenant isolation, auth, webhook signatures, and WhatsApp transport.
- **trycompai/comp** — README blob `7dd3492f20179b6aa83ba83e01270366f48876aa`; GitHub license metadata is AGPL-3.0. Compliance SaaS alternative requiring auth and cloud credentials; README includes setup instructions referencing default credentials. **Disposition:** no runtime relevance to AURELIA; check license obligations and rotate/reject any defaults before a separate sandbox evaluation.

### UI, mobile, education, compilers, dependency tooling, and deployment references

- **styled-components/styled-components** — package manifest blob `377c960586f6595e5ee5585303a40f8cc7853de6`, MIT. UI library; root manifest contains a `postinstall` lifecycle script that runs `generateErrors`. **Disposition:** potential UI dependency only if a product needs it; do not run package install scripts from a branch without reviewing and pinning the package graph.
- **material-components/material-components-android** — Apache-2.0; repository describes itself as in maintenance mode. Android UI library, no AURELIA trading-runtime relevance. **Disposition:** optional Android UI reference only.
- **android/compose-samples** — Apache-2.0; official Jetpack Compose sample collection. **Disposition:** educational/UI reference only; do not transplant sample configuration into production without review.
- **brillout/awesome-react-components** — CC0-1.0 curated directory, not a single executable library. **Disposition:** discovery/reference only; individually review and license-check any linked component before use.
- **AkashSingh3031/The-Complete-FAANG-Preparation** — MIT educational DSA/interview notebooks and materials. **Disposition:** learning reference only; notebooks and copied snippets are not production dependencies.
- **google/comprehensive-rust** — Apache-2.0 Rust course. **Disposition:** educational reference only.
- **AbsInt/CompCert** — formally verified C compiler; GitHub API did not return an SPDX license identifier. **Disposition:** no use proposed; verify license and supported toolchain if ever relevant. Formal verification of a compiler does not certify AURELIA strategy or runtime correctness.
- **ARM-software/ComputeLibrary** — C++ CPU/GPU computer-vision and ML primitives; GitHub metadata did not return an SPDX license identifier. **Disposition:** no direct relevance to the current AURELIA runtime; verify the actual license and target architecture before any future use.
- **compiler-explorer/compiler-explorer** — BSD-2-Clause interactive compiler/assembly service. It executes compilers and processes user-supplied source; a self-hosted instance would be a separate service-security project. **Disposition:** developer education/debugging only; do not expose it with secrets or treat it as a trading dependency.
- **composer/composer** — MIT PHP dependency manager. Package managers execute plugins/scripts and resolve transitive dependencies; no current PHP requirement was established for AURELIA. **Disposition:** no dependency adoption; use only in an isolated PHP project with pinned version and verified package sources if needed.
- **docker/awesome-compose** — CC0-1.0 examples collection, not a single application. Individual samples may expose ports, mount volumes, or include privileged services. **Disposition:** never run the whole repository; inspect and harden each sample before isolated use.
- **docker/compose** — Apache-2.0 container orchestration tooling. Powerful infrastructure dependency, but no need to change AURELIA's existing deployment model was established by this batch. **Disposition:** use the installed/approved version only; do not upgrade production tooling based on this repository intake.
- **ARM-software/ComputeLibrary** and **AbsInt/CompCert** license metadata was absent/NOASSERTION in GitHub API results; this is a verification gap, not a claim that the projects lack a license.

## Inventory snapshot (GitHub API metadata, 2026-10-17)

| Repository | Language | License reported by API | Initial disposition |
|---|---|---|---|
| trycompai/crm | TypeScript | MIT | Separate CRM evaluation only; autonomous PII agent |
| styled-components/styled-components | TypeScript | MIT | UI-only candidate; inspect lifecycle scripts |
| material-components/material-components-android | Java | Apache-2.0 | Maintenance-mode UI reference |
| EveryInc/compound-engineering-plugin | TypeScript | MIT | Pinned development-only skills; disable side effects |
| ericporres/whatsapp-mcp-server | TypeScript | MIT | High risk; local-only test candidate after review |
| Rich627/whatsapp-claude-plugin | TypeScript | Apache-2.0 | High risk; inbound message channel can wake agent |
| ilanbenb/wa_llm | Python | MIT | Block deployment until default credentials eliminated |
| Sealjay/mcp-whatsapp | Go | MIT | High risk; local-only test candidate after review |
| AkashSingh3031/The-Complete-FAANG-Preparation | Jupyter Notebook | MIT | Educational only |
| moltis-org/moltis | Rust | MIT | High privilege; no AURELIA host deployment |
| TitanmindAGI/titanmind-whatsapp-mcp | Python | MIT | High risk; stale, bulk messaging capability |
| devlikeapro/waha | TypeScript | Apache-2.0 | High risk; inspect API exposure and installer |
| melgarafael/DeskcommCRM | TypeScript | MIT | Separate CRM; no installer/credential use |
| FelixIsaac/whatsapp-mcp-extended | Go | MIT | High risk; inspect allowlist and webhooks |
| lgesuellip/langgraph-whatsapp-agent | Python | Apache-2.0 | Twilio template; isolated test only after review |
| felipeadeildo/whatsapp-mcp | TypeScript | GPL-3.0 | High risk; cloud-hosted unofficial client |
| affaan-m/ECC | JavaScript | MIT | Selected pinned dev skills only; no full installer/hooks |
| aldinokemal/go-whatsapp-web-multidevice | Go | MIT | High risk; source review outstanding |
| verygoodplugins/whatsapp-mcp | Go | NOASSERTION | High risk; confirm license and webhook controls |
| AbsInt/CompCert | Rocq Prover | NOASSERTION | License/toolchain verification required |
| ARM-software/ComputeLibrary | C++ | Not returned | License/target verification required |
| compiler-explorer/compiler-explorer | TypeScript | BSD-2-Clause | Developer reference; compiler execution isolation |
| brillout/awesome-react-components | — | CC0-1.0 | Curated links only; review each component |
| google/comprehensive-rust | Rust | Apache-2.0 | Educational only |
| composer/composer | PHP | MIT | No current PHP need; package manager only |
| docker/awesome-compose | HTML | CC0-1.0 | Per-sample review only |
| docker/compose | Go | Apache-2.0 | Existing infra tooling; no upgrade implied |
| trycompai/comp | TypeScript | AGPL-3.0 | Separate compliance product; review license/defaults |
| android/compose-samples | Kotlin | Apache-2.0 | Android UI reference only |
| ComposioHQ/composio | TypeScript | MIT | External-action tool layer; minimal allowlist only |

## Completion gaps and next acceptance criteria

This intake does **not** claim full audits of all 30 repositories. Before any candidate is approved for development use, record its immutable commit SHA and source tree, inspect license files and lockfiles, run secret/SAST/dependency scans in isolation, test auth and network boundaries, and document a reproducible report. WhatsApp candidates additionally need a threat model for linked-device credentials, inbound prompt injection, group/contact PII, outbound-message authorization, webhook authentication/replay, and account-policy risk.

Before PR #159 can merge, the existing independent-review and GitHub protection blockers in Issue #160 must be resolved. No changes were made to AURELIA's capital plane, Layer 6 risk authority, broker credentials, live-order settings, or live-trading lock.
