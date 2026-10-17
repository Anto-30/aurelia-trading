# Third-Party Trading and Agent-Skills Review

**Status:** Research assessment only; no third-party code is approved for production use.  
**Reviewed:** 2026-10-17  
**Target:** AURELIA, canonical repository `Anto-30/aurelia-trading`

## Decision

Use the Vercel Skills ecosystem as a candidate *development-time* skills distribution mechanism only after a pinned-version security review. Do not install or execute skills automatically in production, and do not give skills or language-model agents authority over AURELIA's capital plane, risk decisions, broker credentials, or release authorization.

The crypto-trading-bot repository is a source of architectural ideas only. It explicitly describes itself as not production ready. The design-system pipeline is optional and should be used only if AURELIA's UI work justifies it. The skills CLI security PoC is an audit lead, not proof that every reported issue affects the current upstream version.

## Repository-by-repository disposition

| Repository | Potential value | Disposition |
| --- | --- | --- |
| [Haehnchen/crypto-trading-bot](https://github.com/Haehnchen/crypto-trading-bot) | CCXT exchange adapters, candle storage, strategy plug-ins, dashboard and notification concepts | Research only. Do not import its order execution, risk logic, or strategies as qualified AURELIA components. Its README warns that it is not production ready. |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | CLI for discovering and installing skills for supported coding agents | Candidate development tool, pending pinned-commit review and isolated tests. Never run unreviewed install/update operations against a host with production secrets. |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | React/Next.js performance, web-design, writing, and related engineering guidance | Select individual skills after reviewing their instructions, scripts, dependencies, and source revision. Do not install every skill by default. |
| [vercel-labs/design-systems-to-agent-skills](https://github.com/vercel-labs/design-systems-to-agent-skills) | Generates design-system references from actual source code and verifies generated artifacts | Optional UI-engineering workflow. Run only against a trusted, pinned design-system checkout; keep generated artifacts separate from trading logic. |
| [dimasma0305/skills-cli-poc](https://github.com/dimasma0305/skills-cli-poc) | Reports possible command-injection and symlink-following risks in the Skills CLI | Security test lead only. Do not execute PoC scripts on a developer or production host. Independently reproduce against a pinned upstream revision before classifying severity or affected versions. |

## Findings and limitations

1. **Trading bot is not a production dependency.** Its own README says it is not production ready. CCXT support for many exchanges does not establish suitability for Deriv synthetic indices, contract specifications, execution quality, or AURELIA's risk gates.
2. **Agent skills are executable supply-chain inputs.** A skill may include scripts, shell commands, references, or instructions that influence an agent. A repository being popular or published by a known organization is not a substitute for reviewing the exact commit and files.
3. **The security PoC needs reproducible verification.** The PoC describes a Windows command-injection path through a project lockfile and a symlink-copying path. This review has not reproduced either exploit and does not declare the reported severity or affected-version range confirmed.
4. **Current upstream installer code warrants a symlink-boundary test.** In the reviewed upstream `src/installer.ts`, `copyDirectory` calls `cp` with `dereference: true` and `recursive: true` for non-directory entries, including symlink entries. This can follow a symlink target during copy; whether that yields exploitable disclosure depends on the complete path, exclusions, platform, permissions, and installed files. Add regression tests before relying on copy-mode isolation.
5. **The Windows claim remains unverified here.** A static scan of the current `src/cli.ts` did not locate the exact `spawnSync` / `shell: true` pattern described in the PoC. This is not proof that no equivalent vulnerable path exists elsewhere in the repository; trace the current call graph and test the exact pinned revision.
6. **No complete security or runtime validation was performed.** This was a remote source review of README and selected source content. No full clone, dependency installation, dynamic exploit reproduction, end-to-end trading test, or production deployment was performed.

## Required adoption gate

Before enabling the Skills CLI in an AURELIA development workflow:

- Pin the upstream commit or package version and record its integrity.
- Review the complete install/update call graph, subprocess invocation, lockfile parsing, path normalization, symlink handling, archive extraction, and excluded-file rules.
- Add isolated regression tests for malicious lockfile values on Windows and symlinks targeting files/directories outside the source tree on supported platforms.
- Run tests in a disposable, unprivileged environment with no broker tokens, SSH keys, cloud credentials, or production secrets.
- Use least-privilege, read-only repository access during assessment. Never print or forward authentication tokens.
- Review every selected skill's `SKILL.md`, scripts, references, external network behavior, and transitive dependencies before pinning it.
- Require code review, CI checks, and an explicit release gate before any resulting change can be merged or deployed.
- Keep all skills outside the live runtime and deny agents direct access to broker credentials, order-placement APIs, and capital-plane controls.

## AURELIA boundary conditions

This assessment does not alter AURELIA's canonical runtime or create a second trading engine. Layer 6 remains the deterministic risk authority. Research output must pass data-quality, cost, out-of-sample, calibration, and strategy qualification gates before it can be considered for deployment. No repository in this review qualifies a strategy or authorizes live orders.

## Source links

- [Crypto trading bot README](https://github.com/Haehnchen/crypto-trading-bot)
- [Vercel Skills CLI](https://github.com/vercel-labs/skills)
- [Vercel Agent Skills](https://github.com/vercel-labs/agent-skills)
- [Design systems to agent skills pipeline](https://github.com/vercel-labs/design-systems-to-agent-skills)
- [Skills CLI security PoC](https://github.com/dimasma0305/skills-cli-poc)
- [Skills CLI installer source](https://github.com/vercel-labs/skills/blob/main/src/installer.ts)
- [Skills CLI source](https://github.com/vercel-labs/skills/blob/main/src/cli.ts)
