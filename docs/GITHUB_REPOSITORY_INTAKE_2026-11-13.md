# GitHub repository intake and source review — 2026-11-13

## Scope and result

The user supplied 99 distinct GitHub repository candidates in this batch. The canonical AURELIA external-source registry already contained 5: `QwenLM/qwen-code`, `yetone/magpie`, `openinterpreter/openinterpreter`, `ChromeDevTools/chrome-devtools-mcp`, and `mindsdb/mindshub`.

This change stages 4 additional source records and refreshes 5 existing upstream pins. It does **not** clone repositories, install dependencies, execute upstream code, install a global Claude runtime, or deploy infrastructure. The complete scheduled registry sync workflow has not been run.

## Added or refreshed

| Source | AURELIA mode | Treatment |
|---|---|---|
| `GoogleChrome/modern-web-guidance` | `TOOLCHAIN_ONLY` | Official modern web platform skill source. A project-scoped Claude Code skill is staged at `.claude/skills/modern-web-guidance/SKILL.md`. Upstream CLI not installed or executed. |
| `opensandbox-group/OpenSandbox` | `SANDBOX_ONLY` | Candidate isolated execution substrate. Full runtime, image, egress, credential-vault, and audit review required before use. |
| `microsoft/playwright-mcp` | `REFERENCE_ONLY` | Official browser-MCP comparison only. Existing AURELIA sources already include Chrome DevTools MCP and Playwright CLI workflows; no second browser MCP is configured. |
| `MoonshotAI/kimi-code` | `SANDBOX_ONLY` | Official Kimi Code source pin refreshed. Shell-capable agent; no new runtime or repository-write permissions granted. |
| `QwenLM/qwen-code` | `SANDBOX_ONLY` | Existing source pin refreshed. |
| `ChromeDevTools/chrome-devtools-mcp` | `TOOLCHAIN_ONLY` | Existing source pin refreshed; browser-data exposure and opt-out of usage metrics must be considered before runtime setup. |
| `openinterpreter/openinterpreter` | `SANDBOX_ONLY` | Existing source pin refreshed; computer-use and command-execution capabilities remain isolated and pending security review. |
| `yetone/magpie` | `TOOLCHAIN_ONLY` | Existing source pin refreshed; community toolchain source, pending review. |
| `mindsdb/mindshub` | `SANDBOX_ONLY` | Existing source pin refreshed; memory/knowledge runtime remains sandbox-only and pending data-isolation review. |

All listed head pins were obtained from the GitHub commits endpoint for each repository's default branch on 2026-11-13. A pin establishes provenance only; it is not an attestation that source code is safe.

## Material findings and deferrals

- **Kimi CLI is archived.** MoonshotAI archived `MoonshotAI/kimi-cli` on 2026-09-23. It should not be newly installed; the skill registry marks it `ARCHIVED_DO_NOT_INSTALL` and points to Kimi Code as its maintained successor.
- **OpenClaw is not admitted for installation.** Its gateway and host-facing agent capabilities require a dedicated threat model and isolated evaluation. An absence of active advisories does not remove the risk of host, plugin, browser, and tool permissions.
- **vLLM is not admitted for deployment in this change.** Public advisories include recent issues involving denial of service and untrusted input handling; any future deployment requires version-specific advisory matching, a fixed release, authentication, network controls, and resource isolation.
- **Playwriter is not admitted for AURELIA browser use.** It controls a user's existing Chrome profile, including logins, cookies, and extensions; that is inappropriate for a system that may handle broker or personal sessions.
- **AWS Emulator is deferred.** Its README describes it as a build/test emulator and says not to use it for production workloads or security testing. AURELIA's current deployment is self-hosted Linux/Docker, and an AWS integration need was not established.
- **Microsoft Playwright MCP stays reference-only.** Its README distinguishes MCP's persistent exploratory workflows from CLI-plus-skills for coding-agent throughput. AURELIA already tracks browser CLI and Chrome DevTools MCP, so another browser-control server would add overlap and session risk.
- **Model-serving and proxy sources** (including vLLM, Mooncake, Kimi model repositories, and unofficial Kimi API bridges) are not installed. Compute, licensing, API credential, egress, and model provenance requirements have not been established.
- **General agent frameworks, terminal bridges, device-control tools, MCP registries, DevOps examples, roadmaps, and unrelated app libraries** remain deferred pending a concrete use case and source-specific dependency, permission, network, update, and license reviews.

The remaining user-supplied candidates have not been promoted to the active federation by this change. This is not a claim that they are malicious or unusable; it means their full source audit and a concrete AURELIA integration need were not established in this intake.

## Security and authority invariants

- External code execution remains `DENY_BY_DEFAULT`.
- No external repository, skill, plugin, MCP server, or coding agent receives capital authority, broker access, production-secret access, live-lock mutation, order submission, or production deployment authority.
- No upstream repository was cloned, no package was installed, and no upstream code was run.
- `config/LIVE_LOCK.yaml` was not changed: `LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`, `FINAL_EXECUTION_AUTHORIZATION=false`.
- The Claude skill is staged on this feature branch only. It becomes active for project Claude Code sessions only after review/merge and local checkout synchronization.

## Review status

This is a partial source/provenance triage, not a full code-level security certification. OpenSandbox, Kimi Code, Open Interpreter, Qwen Code, Chrome DevTools MCP, Magpie, and Mindshub still require designated security/dependency/runtime reviews before installation or execution.

## Additional candidates — 2026-11-13

| Source | AURELIA mode | Assessment |
|---|---|---|
| `devmuaz/CoreDeck` | `REFERENCE_ONLY` | MIT-licensed C++20 desktop GUI for Android SDK, AVD, ADB, APK inspection/signing and JDK keystore workflows. This does not solve an AURELIA trading/runtime requirement. ADB shell, file transfer, port forwarding, SDK downloads and signing are host/device-impacting capabilities. No `SECURITY.md` was found during this review. Not installed or assigned to an agent. |
| `marp-team/marp-core` | `TOOLCHAIN_ONLY` | MIT-licensed Markdown-to-slide HTML/CSS renderer. Useful for optional technical documentation and presentation generation, not trading runtime. Upstream main documents v5.0.2 as a release candidate; use the v4 branch / stable 4.x line for any future production documentation pipeline, not `@next`. Known XSS/sanitization advisory history requires version-specific dependency verification and strict sanitization of untrusted Markdown/HTML. No package installed. |

Source pins were read from the GitHub default-branch commits endpoints on 2026-11-13: CoreDeck `384ea0c806203648ca1e0ba4ccccb82b9846ce78`; Marp Core `01ef3a4ef0888403097e2c8f7988ea71c460cf97`. CoreDeck's latest README describes device and ADB operations; Marp Core's README explicitly identifies v5 as a release candidate and documents optional plugins. The GitHub security page did not expose a SECURITY.md for either repository; Marp Core has a published moderate XSS advisory history. These are triage findings, not full code audits.
