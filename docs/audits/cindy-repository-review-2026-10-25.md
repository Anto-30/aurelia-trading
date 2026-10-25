# Cindy Repository Review — 2026-10-25

**Candidate:** [makecindy/cindy](https://github.com/makecindy/cindy)  
**Reviewed branch:** `main`  
**Review scope:** Repository metadata, README, package manifest, contributor guidance, security disclosure policy, and docs index. This is a limited static review, not a full source audit.

## Decision

**Conditional development-tool candidate; do not integrate into AURELIA's trading runtime.** Cindy is an open-source desktop/mobile AI-agent client and orchestration surface, not a trading strategy, risk engine, broker adapter, or AURELIA backend. Its possible value is as a separate human-operated development workspace for agent-assisted research and coding. AURELIA does not need it as a production dependency.

## What the repository says

- The root project identifies itself as the Cindy desktop/mobile client monorepo; the server is maintained in a separate repository and is outside this source tree.
- The client supports multiple harnesses, including Claude Code and Codex, with shared task context, memory, skills, tools, browser/computer/phone control, and task automation.
- Default behavior connects to Cindy's official cloud services when signed in. The README says that “Skip Sign-In” runs local agents but disables server-backed capabilities; it does not mean the app is connected to a locally hosted Cindy backend.
- Root `package.json` declares Apache-2.0, Node `>=22.12`, pnpm `>=10.7 <11`, and a pinned pnpm 10.33.2 package-manager version. It is a substantial pnpm monorepo, not a small library to add to Python trading services.
- The README describes official distribution builds as sending aggregate product analytics (device/OS/app-version metadata associated with the account ID after sign-in) and an online heartbeat. It says chat content, file content, and working-directory data are not collected by those analytics. Self-built desktop builds can remove analytics; mobile analytics is inactive without build-time credentials.
- The project has explicit documentation areas for Electron process boundaries, local credentials/storage, plugin sandboxing, agent behavior, log redaction, and third-party license/SBOM notices. These are useful review entry points, not independent proof that all controls are effective.
- Security issues should be reported privately under the repository's security policy, not disclosed in a public issue or PR.

## Fit for AURELIA

| Area | Assessment | Decision |
|---|---|---|
| Development-time agent orchestration | Potentially useful to coordinate coding/research harnesses | Trial only in a separate, non-production workspace |
| Repository/code editing | High-capability local file and tool access is useful but increases blast radius | Use a disposable worktree, least-privilege account, and explicit allowlisted directories |
| Trading runtime | Desktop/mobile client is not a runtime dependency or deterministic risk authority | Exclude |
| Capital and execution | No agent client may authorize orders or change risk gates | Explicitly deny access to broker credentials, live tokens, execution APIs, and production secret stores |
| Hosted service/privacy | Default signed-in behavior reaches official cloud endpoints; service/backend is separate from this repo | Assess account, data residency, endpoint, and organizational policy before use; do not assume the client is fully self-hostable |
| Licensing | Repository client is Apache-2.0, but dependencies, binaries, model weights, datasets, prompts, and trademarks can have separate terms | Preserve notices; review generated SBOM and third-party notices before redistribution or packaging |

## Required controls before any trial

1. Pin the exact commit and inspect the complete source paths that implement agent tool invocation, subprocesses, browser/computer control, plugin sandboxing, credentials, update delivery, and telemetry.
2. Review `docs/dev-rules/electron-security-and-process-boundaries.md`, `docs/dev-rules/credentials-and-local-storage.md`, `docs/dev-rules/plugin-security-and-authoring.md`, `docs/dev-rules/maker-core-and-agent-behavior.md`, `docs/dev-rules/log-upload-and-redaction.md`, and `docs/legal/README.md` at the pinned revision.
3. Run in a disposable OS user/worktree or isolated VM, with no access to production credentials, `.env` files, Deriv tokens, cloud secret managers, or the AURELIA execution host.
4. Give tools read-only repository access first. Require explicit human approval for writes, shell execution, external network calls, and any action affecting shared repositories.
5. Test deny-by-default tool permissions, path traversal and symlink handling, prompt/tool injection, untrusted repository instructions, credential redaction, and whether browser/computer automation can reach authenticated production sessions.
6. Confirm outbound endpoints, update mechanisms, analytics behavior, and data-handling terms for the actual build and account mode. Do not assume the public client source contains the separately hosted backend.
7. Keep all outputs in the research plane. No direct or indirect path from Cindy or any connected agent to Layer 6 risk authority, the capital plane, live execution, release authorization, or production secrets.
8. Verify the pinned revision's license notices, SBOM, dependency audit, and required test suite before distribution or integration.

## Evidence and limitations

- Repository metadata and selected documentation/manifest files were read through GitHub at the `main` branch on 2026-10-25.
- The public README states Apache-2.0 for the client and describes hosted service behavior and analytics; those statements have not been independently verified against network traces or a built release.
- No clone, dependency install, source execution, security scan, SBOM generation, or automated test run was performed for Cindy. No security certification or runtime compatibility is claimed.

## Final disposition

**Accept for further evaluation as an optional, isolated development-time agent client only. Reject as a production trading dependency.** This assessment adds documentation to AURELIA's external repository review; it does not install Cindy, connect its agents to AURELIA, modify runtime code, expose credentials, or change the fail-closed live lock.
