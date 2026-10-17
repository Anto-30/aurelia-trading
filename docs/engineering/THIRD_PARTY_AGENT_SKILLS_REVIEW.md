# Third-Party Trading and Agent-Skills Review

**Status:** Research assessment only; no third-party code is approved for production use.  
**Reviewed:** 2026-10-17  
**Target:** AURELIA, canonical repository `Anto-30/aurelia-trading`

## Decision

Do not add third-party trading-bot code or agent skills to AURELIA's production runtime. The Vercel Skills CLI is not approved for installing untrusted skills on a host containing credentials until its copy-mode symlink issue is fixed or disabled, and name-collision behavior is made fail-closed. The CLI's Windows command-injection claim is confirmed in a historical source revision but was not found in the current pinned `src/cli.ts` inspected below.

Agent skills may be considered as read-only development references after pinning and content review. They must not have authority over AURELIA's capital plane, risk decisions, broker credentials, deployment secrets, or release authorization.

## Repository-by-repository disposition

| Repository | Potential value | Disposition |
| --- | --- | --- |
| [Haehnchen/crypto-trading-bot](https://github.com/Haehnchen/crypto-trading-bot/tree/cb9563344a20ea7ac89ff214d350f141d1521219) | CCXT exchange adapters, candle storage, strategy plug-ins, dashboard and notification concepts | Research only. Its README says it is not production ready. Do not import execution, risk logic, or strategies as qualified AURELIA components. |
| [vercel-labs/skills](https://github.com/vercel-labs/skills/tree/13e4063a1cf913f5606d57d42ab83a86f5001e04) | CLI for discovering and installing skills | **Blocked for untrusted skill installs/copy mode.** A safe primitive-level symlink reproduction succeeded; see results below. Use only after the symlink boundary and duplicate-name risks are addressed. |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278) | Engineering guidance for React/Next.js and UI review | Selective, development-time use only. The React guidance is static Markdown; web-design guidance currently fetches a mutable `main` URL and must be pinned before use. |
| [vercel-labs/design-systems-to-agent-skills](https://github.com/vercel-labs/design-systems-to-agent-skills/tree/0e541bc7a8eb8e86e6b1c93fac7cf21588d487da) | Extracts design-system facts into skill references | Optional UI-only workflow. Not a trading dependency. Review generated artifacts before use and keep them outside trading/risk code. |
| [dimasma0305/skills-cli-poc](https://github.com/dimasma0305/skills-cli-poc/tree/e63c9e756ddf39bb269bac221597a72067784e05) | Security PoC for command injection and symlink following | Security test lead only. PoC repository commit is unsigned. Do not run its payload scripts on developer or production hosts. |

## Pinned revisions reviewed

| Item | Revision / content hash | Review result |
| --- | --- | --- |
| Skills CLI | `13e4063a1cf913f5606d57d42ab83a86f5001e04`; package version in `package.json`: `1.7.2` | Current-source static inspection; not cloned, installed, or built end-to-end. |
| Skills CLI PoC | `e63c9e756ddf39bb269bac221597a72067784e05` (unsigned) | README and claimed paths inspected; payload scripts were not executed. |
| Agent skills | `063bee94c3f4df8453406c830b0a7df0f2860278` | Reviewed `react-best-practices/SKILL.md` blob `237988de4a66dd8a71d30a2c24ebe1a86b58d04e` and `web-design-guidelines/SKILL.md` blob `ceae92ab319216a68274168fba9b63b998b65997`. |
| Web Interface Guidelines | `434b7f91364665f2f733b310ec54809bf8f37937`; `command.md` blob `3eb3a212b7b89493922ea418489d4c6f67ae8bd5` | Pin this revision instead of following the skill's mutable `main` URL. |
| Design-system pipeline | `0e541bc7a8eb8e86e6b1c93fac7cf21588d487da` | README workflow reviewed; pipeline not executed. |
| Crypto trading bot | `cb9563344a20ea7ac89ff214d350f141d1521219` | README reviewed; bot not installed or executed. |

## Security findings and reproduction

### 1. Windows command-injection claim

The PoC describes a poisoned project `skills-lock.json` feeding a `source` value into `spawnSync` with `shell: process.platform === 'win32'`. The claim is grounded in the historical upstream source revision `3d0f855`: `src/cli.ts` contains the project update call at lines 746-749 and the shell option at line 749. This establishes that the reported dangerous pattern existed in that revision.

In the current pinned upstream `13e4063a1cf913f5606d57d42ab83a86f5001e04`, a full-file static scan of `src/cli.ts` found no `spawnSync` or `shell:` occurrence. Therefore, the exact command-injection pattern is **not present in that inspected current source file**. I did not run the Windows PoC, did not reproduce command execution, and did not verify every published package/version or every other subprocess path. Do not generalize this result to all releases.

### 2. Symlink-copy boundary

The current pinned `src/installer.ts` contains `copyDirectory()`, which calls Node's `cp(srcPath, destPath, { dereference: true, recursive: true })` for non-directory entries, including symlink entries. The exclusion filter checks entry names; it does not establish that a symlink target remains within the source tree.

**Isolated primitive-level reproduction:** in a temporary Linux directory, Node.js `v22.16.0`, I recreated the relevant copy pattern. A symlink inside a mock skill directory pointed to a benign marker file in a separate directory outside that source tree. After the copy, the marker's contents were present under the copied installation directory. Result: **REPRODUCED at the filesystem-primitive level**.

This test used a benign marker only; it did not access secrets, execute the upstream CLI, install a skill, or demonstrate actual exfiltration through an agent. Full end-to-end exploitability remains unverified. Nonetheless, copying arbitrary symlink targets across the source boundary is enough to block copy-mode installation of untrusted skills until a realpath-boundary check or symlink rejection is implemented and tested.

### 3. Duplicate skill-name resolution

A public report describes a malicious skill claiming the same frontmatter `name` as a legitimate skill. In the current pinned `src/skills.ts`, `discoverSkills()` maintains `seenNames`; unless callers explicitly set `includeDuplicateNames`, duplicate names are skipped after the first match. `parseSkillMd()` validates that `name` and `description` are strings but the inspected code does not require the name to match the skill directory basename. This leaves ambiguity/order dependence in the default discovery path. I did not run the complete CLI reproduction. Treat name-only installation from mixed-trust repositories as unsafe; require exact repository/path selection or fail closed on duplicate names and directory/name mismatches.

### 4. Selected skill content

- **React best practices:** inspected the complete selected skill directory at the pinned commit: `SKILL.md`, `AGENTS.md`, `README.md`, `metadata.json`, and 72 entries under `rules/`. The selected skill directory contains Markdown/JSON guidance, not executable scripts or package manifests; a text scan of the 3,811-line compiled `AGENTS.md` found no shell/process/network/secret-handling instructions beyond a documented example command and reference URLs. The repository-root `package.json` declares `yaml: 2.9.0`, but there is no root `pnpm-lock.yaml` at this pin; do not install/build the repository as part of adopting the skill. Approve only the pinned static files as a read-only UI engineering reference, not as a trading strategy or risk authority. This is content/dependency-manifest review, not a formal transitive dependency vulnerability scan.
- **Web design guidelines:** its entire selected directory contains only `SKILL.md`, with no scripts or package manifest. The instructions nevertheless tell the agent to fetch `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` before each review. That mutable URL can change after the skill is pinned. Conditional approval only if the fetch target is replaced with the inspected fixed revision: [pinned command.md](https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md), or if the pinned content is vendored and hash-checked. Do not allow arbitrary URL fetches or execution of downloaded content without review.
- **Design-system pipeline:** use only for UI/design-system documentation, not strategy logic, broker adapters, risk logic, or deployment secrets.

## Required adoption gate

Before enabling the Skills CLI in any AURELIA development workflow:

- Pin a commit/package and record its integrity; do not use floating `main` references for approved inputs.
- Reject symlinks during skill copy, or resolve every target and prove it remains inside the source root; test file and directory links on each supported OS.
- Reject duplicate skill names and require frontmatter names to match directory names, or require explicit source-path disambiguation.
- Audit every subprocess invocation and lockfile parser on Windows and Unix; test malicious values without executing arbitrary payloads.
- Run full regression tests in a disposable, unprivileged VM/container with no broker tokens, SSH keys, cloud credentials, or production secrets.
- Review each skill's complete file tree, scripts, references, external network behavior, and transitive dependencies; do not treat a clean `SKILL.md` as a whole-package audit.
- Require CI, independent human review, and explicit release authorization before merge or deployment.
- Keep skills outside the live runtime. Agents must not control Layer 6, broker credentials, order-placement APIs, or release authorization.

## AURELIA boundary conditions

This review adds no second trading engine and does not modify the canonical runtime, broker credentials, execution settings, or live-trading authorization. Layer 6 remains the deterministic risk authority. Research must pass data-quality, transaction-cost, out-of-sample, calibration, and strategy-qualification gates before any strategy can be considered for deployment. None of these repositories qualifies a strategy or authorizes live orders.

## Additional CI credential-boundary finding (2026-10-17)

A review of AURELIA GitHub Actions exposed a separate but relevant supply-chain control gap. Before this PR's workflow change, `.github/workflows/aurelia-assurance.yml` attached its primary job to the `production` environment while that job ran for `pull_request` events and pushes to any branch. The workflow checked out the event's code and passed protected Deriv credentials to scripts in later steps. If a same-repository PR or branch could run those steps with production environment secrets, modified scripts could potentially disclose them. This structural exposure does not prove that credentials were accessed or exfiltrated.

This PR separates assurance CI (no production environment and no secret expressions) from `protected-deriv-evidence`, which requires a successful assurance job, a push to `refs/heads/main`, and all three repository variables to be explicitly `true`: `AURELIA_PRIVILEGED_CREDENTIAL_JOBS_ENABLED`, `AURELIA_MAIN_BRANCH_PROTECTION_VERIFIED`, and `AURELIA_PRODUCTION_ENVIRONMENT_REVIEWER_GATE_VERIFIED`. The same three-flag gate is applied to credential-bearing jobs in the protected workflow set. Unset variables make those jobs skip; do not set them until main-branch enforcement and production-environment approval settings are verified. It also adds a main-ref guard to credential-bearing jobs in:
- `.github/workflows/aurelia-free-runtime.yml`
- `.github/workflows/deriv-auth-evidence.yml`
- `.github/workflows/deriv-session-verification.yml`
- `.github/workflows/deriv-verify-only-lifecycle.yml`
- `.github/workflows/secret-presence-report.yml`
- `.github/workflows/self-hosted-runtime-deploy.yml`

A regression test, `tests/test_protected_workflow_gates.py`, was added to the existing unittest suite. It scans every `.yml` and `.yaml` workflow under `.github/workflows/`, asserts the pull-request assurance job has no production environment or secret expressions, and verifies that each credential-bearing/production-environment job has the main-ref check and all three explicit owner-verification flags. The existing assurance workflow discovers it through `python -m unittest discover -s tests -p 'test_*.py' -v`.

These main-ref and explicit variable gates are defense in depth, not a substitute for repository-enforced branch protection. A GitHub API read showed both visible repository rulesets are disabled: `All access` (ID `25165036`) contains no rules; `Execution` (ID `24423833`) is disabled and has an empty required-status-check list and empty required-deployment list. The connected API returned 403 for the classic branch-protection endpoint, so classic protection could not be verified. Do not assume `main` is protected based on these observations.

**Remaining repository-owner control:** enable and verify a main-branch ruleset or branch protection; leave all three credential-job variables unset until the controls below have been verified; require pull requests, at least one independent approval, and the relevant successful checks; disallow force-push and deletion; and configure the GitHub `production` environment to require an authorized reviewer before releasing protected environment secrets. The current connected GitHub actions expose ruleset reads but not ruleset/protection mutations, so this review could not safely apply those repository settings. No third-party skill or trading-bot code is approved for production runtime.


## Additional repository intake (2026-10-17)

The following **37 unique repositories** were supplied in the follow-up intake (the duplicate `ComposioHQ/composio` entry is counted once). This is a reproducible **triage pass**, not a claim that all 37 codebases have undergone a full security audit. Repository metadata and selected README material were inspected through GitHub; each entry is pinned to a commit returned by the repository API so the reviewed reference can be revisited. No repository was cloned, installed, built, deployed, or granted credentials in this pass. The environment could not resolve GitHub from the local shell, so end-to-end local builds and dependency scans remain unverified.

### Messaging, WhatsApp, CRM, and personal-agent servers

| Repository pinned to commit | Intended value | Initial disposition and key gate |
| --- | --- | --- |
| [trycompai/crm](https://github.com/trycompai/crm/tree/6d4793dd6d7aeea91aa6a034e00b17d7408a2d08) — `6d4793dd6d7aeea91aa6a034e00b17d7408a2d08` | Agent-oriented CRM | **Reference only.** Separate product application; do not add its auth, CRM writes, or dependencies to AURELIA runtime. |
| [melgarafael/DeskcommCRM](https://github.com/melgarafael/DeskcommCRM/tree/e36bfc9e8a54e5d9a2596d69f10f1725f7694be0) — `e36bfc9e8a54e5d9a2596d69f10f1725f7694be0` | Self-hosted AI sales CRM with WhatsApp | **Reference only; high privilege surface.** README describes a one-command installer, Docker services, Supabase credentials, admin setup and WhatsApp integration. Do not pipe remote scripts into a shell or deploy with production credentials before reviewing every install script and compose file. |
| [ericporres/whatsapp-mcp-server](https://github.com/ericporres/whatsapp-mcp-server/tree/62853df9c8b5210c501d8367fcb5dbbda71f2538) — `62853df9c8b5210c501d8367fcb5dbbda71f2538` | WhatsApp MCP reads, searches, exports and sends messages | **Blocked from production use.** README exposes group history, export, backfill, send/reply tools and persistent Baileys auth state; remote HTTP/tunnel mode expands the attack surface. Test only with a dedicated account, synthetic chats, strict authentication, private network binding and explicit send allowlists. |
| [Rich627/whatsapp-claude-plugin](https://github.com/Rich627/whatsapp-claude-plugin/tree/17af8ed8af29aa099ef096ec10d61f6c277d82aa) — `17af8ed8af29aa099ef096ec10d61f6c277d82aa` | WhatsApp channel for Claude Code | **Do not enable in a privileged agent session.** Its README explicitly warns that untrusted inbound chat text can enter the coding-agent session and that combining its development-channel flag with permission bypass could allow remote command execution. Review access controls and keep permission prompts enabled; no `--dangerously-skip-permissions`. |
| [ilanbenb/wa_llm](https://github.com/ilanbenb/wa_llm/tree/b00e88299c176ddb942fc6e338eb1c4ef0a8089b) — `b00e88299c176ddb942fc6e338eb1c4ef0a8089b` | WhatsApp group summary bot with PostgreSQL/pgvector | **Research only.** README documents group monitoring, persisted message history, model/API secrets and optional auto-replies. Requires consent, retention/deletion rules, opt-out validation, secret handling and egress review before any trial. |
| [Sealjay/mcp-whatsapp](https://github.com/Sealjay/mcp-whatsapp/tree/078ac8c5e3f8a6f32c6a5902e4859f86c853330f) — `078ac8c5e3f8a6f32c6a5902e4859f86c853330f` | Go MCP server exposing personal WhatsApp tools | **Research only; no personal-account pairing.** Review every read/write tool, authorization boundary, session-store permissions and remote transport before isolated testing. |
| [TitanmindAGI/titanmind-whatsapp-mcp](https://github.com/TitanmindAGI/titanmind-whatsapp-mcp/tree/2c6afb514bae7e922416dd26ed2aada7f31cfe66) — `2c6afb514bae7e922416dd26ed2aada7f31cfe66` | WhatsApp marketing/messages MCP | **Research only.** Validate official API use, recipient consent, template/window rules, rate limits, data retention and explicit outbound-send authorization. |
| [devlikeapro/waha](https://github.com/devlikeapro/waha/tree/0858b4f0efa5d2afc085c41e3873aae29154f6c0) — `0858b4f0efa5d2afc085c41e3873aae29154f6c0` | WhatsApp HTTP API with multiple engines | **Isolated test only.** README documents QR pairing, HTTP send endpoints and Docker deployment. Never expose the API/dashboard publicly without strong authentication, TLS, network restrictions and secret/session protection; verify official versus unofficial transport and current policy constraints. |
| [FelixIsaac/whatsapp-mcp-extended](https://github.com/FelixIsaac/whatsapp-mcp-extended/tree/e365961e30d50bd42b0aaa7d9539222285258c53) — `e365961e30d50bd42b0aaa7d9539222285258c53` | WhatsApp MCP with message, media, group and account-admin tools | **Research only.** The README exposes send/delete/edit, media, presence, group-management and blocklist operations. Use a least-privilege toolset, recipient allowlist and synthetic account; review webhook/auth and container/network defaults. |
| [felipeadeildo/whatsapp-mcp](https://github.com/felipeadeildo/whatsapp-mcp/tree/7e35463c646f03b3a31a5c72b014ccafcbf92800) — `7e35463c646f03b3a31a5c72b014ccafcbf92800` | WhatsApp MCP deployed to a user Cloudflare account | **Research only.** Cloud account access plus message read/send capabilities require separate scoped credentials, audit logging and an outbound allowlist; no account linking during triage. |
| [aldinokemal/go-whatsapp-web-multidevice](https://github.com/aldinokemal/go-whatsapp-web-multidevice/tree/a63e69069abc31ccbcc9fd48e2630afbe08742b0) — `a63e69069abc31ccbcc9fd48e2630afbe08742b0` | Go WhatsApp REST API, webhooks and MCP | **Isolated test only.** Treat linked-device sessions, webhooks, UI/API authentication and message sending as sensitive. Review deployment defaults and session persistence before any exposure. |
| [verygoodplugins/whatsapp-mcp](https://github.com/verygoodplugins/whatsapp-mcp/tree/895404542017f34a900f9f572a5497c275a96440) — `895404542017f34a900f9f572a5497c275a96440` | WhatsApp MCP read/send integration | **Research only.** Verify license terms (GitHub reports `NOASSERTION`), authentication, send safeguards and the exact upstream implementation before reuse. |
| [lgesuellip/langgraph-whatsapp-agent](https://github.com/lgesuellip/langgraph-whatsapp-agent/tree/69b9bdd341e0c379b5452b8d3d46879c25e660fc) — `69b9bdd341e0c379b5452b8d3d46879c25e660fc` | LangGraph + Twilio WhatsApp agent template | **Reference only.** Last API-returned commit is from 2025; verify maintenance, dependencies, provider behavior and deployment compatibility. Do not grant it access to AURELIA or business messaging accounts. |
| [moltis-org/moltis](https://github.com/moltis-org/moltis/tree/8670f90b075b2aa395068e8e1973b9ca8fef7ff0) — `8670f90b075b2aa395068e8e1973b9ca8fef7ff0` | Persistent multi-channel personal agent server with sandboxing/MCP | **Separate sandbox research only.** Broad channel and tool access means its own sandbox claims need verification; do not place it in the trading process or share broker tokens. |
| [composio-community/openclaw-composio](https://github.com/composio-community/openclaw-composio/tree/8a2ac9703410b642ce88a9252abcc17d3d7e2f5f) — `8a2ac9703410b642ce88a9252abcc17d3d7e2f5f` | OpenClaw fork with Composio integration | **Separate sandbox research only.** A full agent fork has a much larger supply-chain and update surface than a plugin. No install, credential connection, daemon or production deployment approved. |

### Agent skills, plugins, and tool-integration gateways

| Repository pinned to commit | Intended value | Initial disposition and key gate |
| --- | --- | --- |
| [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin/tree/2e41b4490a37f53db0beb6d4904618da9af2f559) — `2e41b4490a37f53db0beb6d4904618da9af2f559` | Engineering workflow plugin for coding agents | **Read-only review first.** Potential development productivity only; inspect every hook, command, agent, shell invocation and external dependency. No production credential authority or automatic deployment. |
| [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/76aaa77df6adc5b889e689007bf99b9a4f74af34) — `76aaa77df6adc5b889e689007bf99b9a4f74af34` | Agent harness, skills, memory and security workflows | **Selective development references only.** Do not import hooks, persistent memory, shell policies or autonomous workflows without per-file review and tests; keep out of the live trading runtime. |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills/tree/be2a406907dbc61b73e6827ded415c96139d13a2) — `be2a406907dbc61b73e6827ded415c96139d13a2` | Curated catalogue of third-party skills/plugins | **Index only, not a trusted allowlist.** The catalogue includes skills that can access browsers, shell, external APIs and connected accounts. Select individual entries, pin their sources and inspect their full trees before use. |
| [ComposioHQ/composio-mcp-plugin](https://github.com/ComposioHQ/composio-mcp-plugin/tree/bbcb9ccce59090642ca6dad5d6f0fa485c303539) — `bbcb9ccce59090642ca6dad5d6f0fa485c303539` | Composio MCP plugin/skills for connected app actions | **Do not connect AURELIA accounts during evaluation.** README describes OAuth-connected actions and remote sandbox execution. Verify tool scopes, tenant isolation, audit/retention terms and authorization semantics; connected apps can perform real writes. |
| [ComposioHQ/composio](https://github.com/ComposioHQ/composio/tree/231122de19abd820eac91549382e407e2d2cbe06) — `231122de19abd820eac91549382e407e2d2cbe06` | Toolkits, authentication, agent sessions and sandbox | **Architecture/reference only.** A platform that can discover, authenticate and execute external actions is a privileged integration plane, not a harmless dependency. No installation or credential linking; require a separate threat model and explicit least-privilege allowlist. |
| [composio-community/openclaw-composio-plugin](https://github.com/composio-community/openclaw-composio-plugin/tree/47025c33224d343d9fbbf67e0a24e56eeaa18fff) — `47025c33224d343d9fbbf67e0a24e56eeaa18fff` | OpenClaw plugin/onboarding for Composio CLI | **Review-only.** README directs users to a remote shell installer and authenticated CLI. Do not pipe installer output to a shell or run authenticated write examples as part of triage. |
| [composio-community/open-dot](https://github.com/composio-community/open-dot/tree/f838e17cf5c3a88ade5ceea54680a8145d048c1d) — `f838e17cf5c3a88ade5ceea54680a8145d048c1d` | Local personal agent with browser automation and approval cards | **Separate developer workstation only after code review.** Persistent logged-in browser state and saved passwords are high-risk. Validate action policy enforcement, prompt-injection boundaries and approval bypass resistance; no unattended production use. |
| [ComposioHQ/trustclaw](https://github.com/ComposioHQ/trustclaw/tree/c07410bccb916236b45b563e8c4ff76ad83d3855) — `c07410bccb916236b45b563e8c4ff76ad83d3855` | Self-hosted personal agent with OAuth tools and sandboxed execution | **Separate sandbox evaluation only.** README describes background/cron actions, external tool integrations and authentication. Sandbox and OAuth claims need independent verification; never grant AURELIA broker, deployment or GitHub write authority. |
| [Anil-matcha/open-agent-connector](https://github.com/Anil-matcha/open-agent-connector/tree/a6c4717c52acd3a5ab30857ed0dd805a4d3dcf15) — `a6c4717c52acd3a5ab30857ed0dd805a4d3dcf15` | Self-hosted MCP/REST integration gateway | **Promising candidate for isolated evaluation, not approved.** README claims scoped runtime tokens, encrypted credentials, SSRF protections and audit logs, but also notes registered provider actions are not all battle-tested. Independently test auth, SSRF/redirect defenses, token scoping, secret redaction and idempotency before any connected account. |

### UI, mobile, build, compiler, and learning references

| Repository pinned to commit | Intended value | Initial disposition and key gate |
| --- | --- | --- |
| [styled-components/styled-components](https://github.com/styled-components/styled-components/tree/379477dabb6875cc7d332269db5da61282d225e9) — `379477dabb6875cc7d332269db5da61282d225e9` | React styling library | **Potential UI dependency only.** Evaluate compatibility, package provenance, license and bundle/server-rendering behavior in a separate UI change; no trading runtime changes. |
| [material-components/material-components-android](https://github.com/material-components/material-components-android/tree/66b0eeb53afeb6025ffbbd37734b08e5bce197ed) — `66b0eeb53afeb6025ffbbd37734b08e5bce197ed` | Android Material components | **Reference only; maintenance mode.** Relevant only to an Android client, not the backend trading runtime. |
| [brillout/awesome-react-components](https://github.com/brillout/awesome-react-components/tree/66b2758c4808d62cfe7c2a1dc0c48f7d51153cf5) — `66b2758c4808d62cfe7c2a1dc0c48f7d51153cf5` | Curated React component directory | **Discovery index only.** Each downstream library needs its own version, license, maintenance and security review. |
| [android/compose-samples](https://github.com/android/compose-samples/tree/5f2f2cf1fdfdb6472dd46deb8bcd35cbc9024632) — `5f2f2cf1fdfdb6472dd46deb8bcd35cbc9024632` | Official Jetpack Compose samples | **Learning/reference only.** Not a production dependency for AURELIA. |
| [AkashSingh3031/The-Complete-FAANG-Preparation](https://github.com/AkashSingh3031/The-Complete-FAANG-Preparation/tree/685cf8a9dde63d6055890d04a330e6f8fe7cd859) — `685cf8a9dde63d6055890d04a330e6f8fe7cd859` | Algorithms and interview preparation | **Learning material only.** No runtime integration; verify individual copied snippets and their licenses if reused. |
| [AbsInt/CompCert](https://github.com/AbsInt/CompCert/tree/e276a3f881669252e2a5c4b5fec06f51f7143161) — `e276a3f881669252e2a5c4b5fec06f51f7143161` | Formally verified C compiler | **Research/reference only.** Formal verification applies to a specified compiler/toolchain and theorem assumptions; it does not certify AURELIA or unrelated code. Confirm license before redistribution (`NOASSERTION` in GitHub metadata). |
| [ARM-software/ComputeLibrary](https://github.com/ARM-software/ComputeLibrary/tree/80bbedb606746dcc1451cffedf3931d9fec3f53c) — `80bbedb606746dcc1451cffedf3931d9fec3f53c` | Arm-optimized computer vision/ML functions | **Not currently relevant to AURELIA's trading runtime.** Consider only if a measurable CPU/ML workload justifies it; then run target-hardware tests and dependency/license review. |
| [compiler-explorer/compiler-explorer](https://github.com/compiler-explorer/compiler-explorer/tree/73b05149ea8d0bdc792d2ebe9e30ee760feaee83) — `73b05149ea8d0bdc792d2ebe9e30ee760feaee83` | Browser-based compiler execution and assembly inspection | **Development/reference only.** A service that executes compilers needs isolation and resource controls; do not host or expose it as an AURELIA service without a separate threat model. |
| [google/comprehensive-rust](https://github.com/google/comprehensive-rust/tree/1b82ec405d6346932e10363248b23cd6e38df050) — `1b82ec405d6346932e10363248b23cd6e38df050` | Rust training curriculum | **Learning material only.** No runtime integration. |

### Build, deployment, compliance, and dependency-management references

| Repository pinned to commit | Intended value | Initial disposition and key gate |
| --- | --- | --- |
| [composer/composer](https://github.com/composer/composer/tree/43f74517021a59ed4054a801c1472ef66355c49a) — `43f74517021a59ed4054a801c1472ef66355c49a` | PHP dependency manager | **Not an AURELIA runtime dependency unless a PHP component is justified.** Treat plugins and install scripts as code execution; review lockfiles and package provenance. |
| [docker/awesome-compose](https://github.com/docker/awesome-compose/tree/30f4b7f6a6c3b0c0ecf4d4efb0de203c48d11562) — `30f4b7f6a6c3b0c0ecf4d4efb0de203c48d11562` | Docker Compose example catalog | **Examples only, never deploy blindly.** Inspect images, privileged mode, bind mounts, exposed ports, capabilities, secrets and volume ownership for each selected sample. |
| [docker/compose](https://github.com/docker/compose/tree/289d8a037874a5197c54cfa055d28cc5d980593f) — `289d8a037874a5197c54cfa055d28cc5d980593f` | Docker Compose tooling | **Existing platform/tooling reference.** No need to vendor the implementation; pin installed versions and validate deployment files independently. |
| [trycompai/comp](https://github.com/trycompai/comp/tree/0117612ce37331e03a45e4b38054d54ed694a57d) — `0117612ce37331e03a45e4b38054d54ed694a57d` | AI-native compliance platform | **Separate product/reference only.** GitHub reports AGPL-3.0; do not copy or link code into proprietary components without license review. Compliance dashboards do not substitute for AURELIA's evidence gates. |

## Cross-cutting findings and disposition

1. **No wholesale imports.** These repositories span unrelated products, education, UI libraries, agent frameworks and messaging gateways. Their star counts or recent activity do not establish security, suitability or production readiness.
2. **WhatsApp integrations are high privilege.** Several expose private message history, media, contact/group administration, persistent linked-device credentials and outbound messaging. Do not pair a personal account, ingest private chats, or send messages as part of this review. Prefer official business APIs where appropriate, use explicit recipient allowlists, consent and retention controls, and never feed inbound messages directly to an agent with unrestricted shell or repository write access.
3. **Agent/plugin integrations can cause real external writes.** Composio and OpenClaw-style projects connect agents to email, CRM, GitHub, storage and other apps. Any eventual test must use a disposable account, narrow scopes, audit logs, approval gates and no AURELIA secrets. A sandbox claim is not a substitute for testing escape boundaries and access control.
4. **License metadata is incomplete for some repositories.** GitHub returned `NOASSERTION` or no SPDX license for some entries; treat this as unresolved, not as permission to copy or redistribute.
5. **No AURELIA production approval is granted.** Nothing in this intake changes the canonical runtime, Layer 6 risk authority, broker authentication, execution firewall, live-order permissions, or release authorization. Use the pinned sources only for the specific research or development purpose described above.

## Source links

- [Crypto trading bot, pinned commit](https://github.com/Haehnchen/crypto-trading-bot/tree/cb9563344a20ea7ac89ff214d350f141d1521219)
- [Vercel Skills CLI, pinned commit](https://github.com/vercel-labs/skills/tree/13e4063a1cf913f5606d57d42ab83a86f5001e04)
- [Historical Skills CLI subprocess source](https://github.com/vercel-labs/skills/blob/3d0f855/src/cli.ts)
- [Current Skills CLI installer, pinned commit](https://github.com/vercel-labs/skills/blob/13e4063a1cf913f5606d57d42ab83a86f5001e04/src/installer.ts)
- [Current Skills CLI discovery source, pinned commit](https://github.com/vercel-labs/skills/blob/13e4063a1cf913f5606d57d42ab83a86f5001e04/src/skills.ts)
- [Vercel Agent Skills, pinned commit](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278)
- [Web Interface Guidelines, pinned commit](https://github.com/vercel-labs/web-interface-guidelines/tree/434b7f91364665f2f733b310ec54809bf8f37937)
- [Design systems to agent skills, pinned commit](https://github.com/vercel-labs/design-systems-to-agent-skills/tree/0e541bc7a8eb8e86e6b1c93fac7cf21588d487da)
- [Skills CLI security PoC, pinned commit](https://github.com/dimasma0305/skills-cli-poc/tree/e63c9e756ddf39bb269bac221597a72067784e05)
- [Public report: skill name collision](https://github.com/vercel-labs/skills/issues/353)
