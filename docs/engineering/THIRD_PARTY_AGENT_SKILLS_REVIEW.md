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

This PR separates assurance CI (no production environment and no secret expressions) from `protected-deriv-evidence`, which requires a successful assurance job and runs only on a push to `refs/heads/main` in the `production` environment when repository variable `AURELIA_PROTECTED_DERIV_EVIDENCE_APPROVED` is explicitly set to `true`. The variable is fail-closed when unset and must not be enabled until main-branch enforcement and production-environment approval settings are verified. It also adds a main-ref guard to credential-bearing jobs in:
- `.github/workflows/aurelia-free-runtime.yml`
- `.github/workflows/deriv-auth-evidence.yml`
- `.github/workflows/deriv-session-verification.yml`
- `.github/workflows/deriv-verify-only-lifecycle.yml`
- `.github/workflows/secret-presence-report.yml`
- `.github/workflows/self-hosted-runtime-deploy.yml`

These job-level guards are defense in depth, not a substitute for repository-enforced branch protection. A GitHub API read showed both visible repository rulesets are disabled: `All access` (ID `25165036`) contains no rules; `Execution` (ID `24423833`) is disabled and has an empty required-status-check list and empty required-deployment list. The connected API returned 403 for the classic branch-protection endpoint, so classic protection could not be verified. Do not assume `main` is protected based on these observations.

**Remaining repository-owner control:** enable and verify a main-branch ruleset or branch protection; require pull requests, at least one independent approval, and the relevant successful checks; disallow force-push and deletion; and configure the GitHub `production` environment to require an authorized reviewer before releasing protected environment secrets. The current connected GitHub actions expose ruleset reads but not ruleset/protection mutations, so this review could not safely apply those repository settings. No third-party skill or trading-bot code is approved for production runtime.

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
