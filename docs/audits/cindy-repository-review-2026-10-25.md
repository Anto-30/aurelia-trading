# Cindy Repository Review — 2026-10-25

**Candidate:** [makecindy/cindy](https://github.com/makecindy/cindy)  
**Reviewed ref:** `main` (mutable; immutable revision not pinned)  
**Decision:** **Conditional development-tool candidate; not approved for AURELIA production or trading runtime.**

## Purpose and fit

Cindy is an open-source desktop/mobile AI-agent client monorepo, not a trading strategy, broker adapter, backtester, risk engine, or execution service. Its possible value is as a separate human-operated workspace for coding, research, and coordinating development agents. AURELIA does not need Cindy as a runtime dependency.

## Static evidence reviewed

Read repository README, `package.json`, `pnpm-workspace.yaml`, `config/endpoint.global.json`, `SECURITY.en.md`, and selected authoritative developer rules for Electron process boundaries, credentials/local storage, plugin security/authoring, agent behavior, and log upload/redaction. This is a targeted documentation/manifest review, not a line-by-line source audit.

- Root manifest declares Apache-2.0, Node `>=22.12`, pnpm `>=10.7 <11`, pinned pnpm `10.33.2`, and a pnpm workspace covering `apps/*` and `packages/*`.
- README identifies `apps/desktop` as Electron, `apps/mobile` as Expo/React Native, shared packages for agent/model/tool integrations, and separately maintained backend services outside this repository.
- The checked-in global endpoint manifest names hosted endpoints for auth, chat, device linking, OAuth broker, object storage, heartbeat, model access, voice, GitHub, plugin/skill hubs, CDN, and mobile updates. A trial must treat the default signed-in build as a networked client; source visibility does not establish that the hosted backend is self-hostable.
- README describes official-build analytics as aggregate device/OS/app-version metadata associated with account ID after sign-in, plus a signed-in heartbeat. It says chat/file/working-directory contents are not included in those analytics and crash dumps are not automatically uploaded. These are repository statements, not independent traffic-capture verification.
- Plugin-security rules define a capability-oriented model, a `.cindy` package format, manifest validation, sandbox/runtime boundaries, and named capability slots for network, filesystem, agent, and other host features. This is design evidence, not independent proof that every runtime path enforces the intended permissions.
- Credential rules explicitly distinguish a trusted Node worker from a security sandbox and warn that a trusted worker is not isolated from malicious code in the same way as a sandboxed plugin.
- Electron rules describe Renderer as untrusted, require restrictive BrowserWindow defaults and IPC sender validation, and treat remote content, plugins, paths, and renderer-supplied identity as untrusted. Implementation-level tests and configuration still need independent verification.
- The README says vendor binaries, including agent CLIs and ripgrep, are fetched during dependency setup; platform-specific integrity handling is noted for Android platform tools. This adds a software-supply-chain surface to pin and verify.
- `SECURITY.en.md` asks reporters to use private vulnerability reporting rather than public issues/PRs for exploitable findings.

## AURELIA integration boundary

| Area | Disposition |
|---|---|
| Development-time agent workspace | Conditional trial only in a disposable VM or isolated OS user/worktree |
| Research/docs/code assistance | Potentially useful with read-only repository access first and explicit human approval for writes, shell, and network actions |
| Production trading runtime | Reject; no runtime dependency required |
| Capital, broker, and release authority | Explicitly deny access; no path to Layer 6, capital plane, live tokens, execution APIs, release authorization, or production secret stores |
| Hosted service / data handling | Confirm privacy, account, region, and endpoint requirements before sign-in; do not assume self-hostability |
| License and redistribution | Root Apache-2.0 applies to repo code except separately licensed assets/dependencies; preserve NOTICE and third-party notices and inspect the actual build SBOM before packaging or redistribution |

## Minimum controls before a trial

1. Pin an immutable commit and verify source integrity before installing dependencies.
2. Use a disposable VM/OS account with no access to production credentials, `.env` files, Deriv tokens, secret managers, authenticated production browser profiles, or the AURELIA execution host.
3. Start with read-only access to a throwaway AURELIA clone. No permission to push, merge, deploy, or invoke production workflows. Allowlist filesystem paths and deny arbitrary shell/network actions unless individually approved.
4. Review plugin runtime, capability authorization, Node worker boundary, subprocess creation, browser/computer-control paths, update delivery, endpoint manifests, and telemetry implementation at the pinned revision. Test prompt/tool injection, hostile repository instructions, path traversal/symlinks, permission escalation, credential redaction, and external-session access.
5. Inspect lockfile and downloaded binary provenance; generate an SBOM and license inventory, run dependency and secret scans, and review Electron/Chromium configuration and IPC sender checks.
6. Confirm network destinations and data handling through configuration review and, if permitted, network observation of the exact build/account mode. Disable analytics in a controlled source build only if policy requires it and the change is understood and tested.
7. Keep all activity in the research plane. Cindy or any connected agent must not authorize capital, alter deterministic risk settings, change `config/LIVE_LOCK.yaml`, or reach live execution.

## Verification status and limits

- GitHub metadata, selected manifest/config files, and selected docs were inspected at `main` on 2026-10-25. Because `main` is mutable, the review is not reproducible until an immutable commit SHA is pinned.
- No clone, dependency install, build, test suite, source execution, SBOM generation, vulnerability scan, license scan, or network capture was performed. No vulnerability-free claim, security certification, performance claim, or compatibility sign-off is made.
- This review did not install Cindy, add dependencies, connect agents to AURELIA, or modify runtime code.

## Final disposition

**Accept only for further evaluation as an optional, isolated development-time agent client. Reject as a production trading dependency.** Preserve AURELIA's fail-closed live lock and canonical deterministic risk authority. Any future trial needs a pinned revision, isolated environment, reviewed permissions, dependency/SBOM evidence, and human-approved access boundaries.
