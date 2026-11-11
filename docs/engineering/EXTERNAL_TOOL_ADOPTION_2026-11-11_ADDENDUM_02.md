# External Repository Intake Addendum — 2026-11-11 (Batch 2)

## Decision

Nine source candidates are recorded: eight newly supplied repository URLs plus the GitHub Action referenced twice in the supplied workflow snippet. The duplicated `penvhq/penv-run@v1.0.0` line is deduplicated to one logical action reference.

No upstream repository, package, skill, action or runtime was installed or executed. The review used GitHub repository metadata, default-branch commit search, README/license/manifests and selected entrypoints. Full source review, SBOM, dependency and security scans, sandbox tests and compatibility tests remain outstanding.

## Repository decisions

| Source | Pinned commit | Licence | Disposition |
|---|---|---|---|
| [technicalindicators](https://github.com/anandanand84/technicalindicators) | `7740f17cf681a2b1ace3009f5f396c14cbadf1f1` | MIT | Reference only; old 2020 head and legacy TypeScript/dependency stack. Indicator names do not validate Deriv synthetic volume semantics. |
| [ai-trader](https://github.com/whchien/ai-trader) | `7681fe331fb638beab1ae20d3552c802bbaa9174` | GPL-3.0 | Research only; no code import before licence compatibility and rigorous backtest/data/MCP audit. |
| [Astryx](https://github.com/meta/astryx) | `c1a1ea82b4cbd0a6b668cc9ce5c75f0cd2647850` | MIT | Reject AURELIA trading-runtime adoption; React/StyleX design system only. |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | `2f1649cefb82f417abbb2712f5397439d010698e` | Apache-2.0 | Sandbox-only browser QA candidate; audit native binary, postinstall and browser/auth boundaries. |
| [improve](https://github.com/shadcn/improve) | `cac56e1ebd3c279aa9153616cfeac7b174ab90f9` | MIT (`LICENSE.md`; skill frontmatter also MIT) | Selective read-only skill candidate; no install until executor worktree isolation is verified. |
| [agent-skills](https://github.com/addyosmani/agent-skills) | `301b02b12bff98e4688e6984af6556802322bbde` | MIT | Selective skill review; no bulk install, especially for /build auto and /ship. |
| [codex-security](https://github.com/openai/codex-security) | `4aa9acc5ce459ae0f525c88f727713694597a7ad` | Apache-2.0 | Priority security-tool evaluation; no CI installation until API-key, source-upload, retention and reporting controls are verified. |
| [TheAlgorithms/Java](https://github.com/TheAlgorithms/Java) | `b2af1db6dcae46521e97a6331eae8cea61933080` | MIT | Educational reference only; not a trading/backtesting dependency. |
| [penv-run](https://github.com/penvhq/penv-run) | `b3067cabb2a758108a9a4b9406bdd555d78d46ee` | MIT | Defer; no workflow change. OIDC secret-delivery action requires complete source/threat-model review. |

## Penv workflow finding

The supplied YAML repeats the same action twice. Keep at most one logical invocation if a future approved use case is established. More importantly:

- The action requests `id-token: write` and executes a supplied command with penv-cloud secrets in that command's environment.
- Its own README says to pin a full 40-character commit SHA, not a tag such as `@v1.0.0`.
- Its action documentation explicitly says it does not protect against a malicious step in the same job; revocation is best-effort.
- The review inspected README, `action.yml`, `package.json`, `main.mjs` and `post.mjs`. API, delivery, revocation implementation and full tests are still unaudited.

Therefore, do not add this action to AURELIA workflows now. Do not provide Deriv, broker or production credentials to it.

## Agent routing

- **ClaudeCode:** primary source reviewer for all nine candidates; inspect manifests, prompts, install scripts, workflows and permissions.
- **JEV:** independent validation of commit pins, licence evidence, SBOMs, tests and security findings. Assignment is not evidence of a connected JEV runtime.
- **GoogleAgentSkills:** security review of browser automation, Codex Security, Penv OIDC/secret handling, and agent skill dispatch boundaries.
- **KimiK3:** quantitative review of indicator formula parity and AI-Trader backtest methodology; no trading conclusions without independent data/cost validation.
- **GrokBot:** adversarial review of AI-Trader research assumptions and agent-skill execution boundaries.
- **PlaywrightCLI:** browser QA only in disposable profiles with synthetic credentials.
- **GLM:** document and design-system scope review.
- **ChatGPT:** supervisory evidence reconciliation in the current session only.
- **AURELIA:** sole policy, risk, capital, execution and release authority. Dev, DeepSeek Harness and Hermes remain NOT_CONNECTED unless separately verified.

## Required gates

1. Review complete source at the pinned commit, including workflows, hooks, scripts, dependencies, licences, network calls and credential handling.
2. Generate SBOM and run licence, vulnerability, secret, static and malware scans in an isolated disposable workspace.
3. Test execution-capable tools for prompt injection, process escalation, filesystem boundary violations, egress, credential leakage and sandbox escape.
4. Require independent review and reproducible evidence before any separate installation PR.
5. Keep all candidates outside AURELIA capital/execution paths. No production secrets, Deriv credentials, broker access, order submission, capital authority, LIVE_LOCK mutation or production deployment.

Machine-readable records:
- `config/external_tool_intake_2026-11-11_addendum_02.json`
- `config/external_repository_agent_assignments_2026-11-11_addendum_02.json`

This is registration and first-pass triage, not installation, certification or authorization.


## Routing integrity correction

During this batch, the earlier 2026-11-11 assignment file was found to contain truncated commit-hash fragments in its `primary` and `reviewers` fields instead of agent role names. It has been repaired to use named primary agents and reviewer arrays for all 11 earlier sources. The corrected batch-1 routing file and this batch-2 routing file are now both referenced by the canonical `config/agent_tool_skill_assignment.json`. This repair corrects metadata only; it does not activate any disconnected agent.


## Targeted source audit update

Selected high-risk entrypoints and tests have now been inspected for Penv, agent-browser, Codex Security, AI Trader, shadcn/improve and selected agent-skills components. Findings and remaining gaps are recorded in `docs/engineering/EXTERNAL_TOOL_AUDIT_STATUS_2026-11-11.md` and the `audit_status` object in the machine-readable addendum. This remains a targeted review, not a full source/security certification: no upstream tests were executed, and no SBOM, dependency, secret, malware or dynamic sandbox scans were run.
