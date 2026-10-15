# Repository Intake — Routing and Admission Record (2026-10-13)

This record summarizes the current candidate routing added to the intake branch. Repository registration is a governance record, not a software installation, agent login, or authorization to execute third-party code. Upstream source pins are listed in `repository-intake-upstream-pins-2026-10-13.md`.

| Repository | Primary route | Supporting reviewers | Registry mode | Admission gate |
|---|---|---|---|---|
| `pasky/chrome-cdp-skill` | PlaywrightCLI | ClaudeCode, GrokBot, JEV, ChatGPT | SANDBOX_ONLY | Disposable browser profile; no authenticated broker session, production secrets, public CDP port or trade actions |
| `anthropics/claude-quickstarts` | ClaudeCode | GrokBot, JEV, ChatGPT | REFERENCE_ONLY | Selective examples only; inspect dependencies, API key handling, shell/network scope |
| `siteboon/claudecodeui` | GoogleAgentSkills | ClaudeCode, PlaywrightCLI, JEV | SANDBOX_ONLY | **Blocked** pending advisory reconciliation and regression tests; AGPL-3.0 review |
| `ChrisWiles/claude-code-showcase` | ClaudeCode | GrokBot, JEV, ChatGPT | REFERENCE_ONLY | License not confirmed at root LICENSE path; inspect every hook/workflow and token scope |
| `decebals/claude-code-java` | ClaudeCode | JEV, ChatGPT | TOOLCHAIN_ONLY | Conditional on Java actually being required; audit setup scripts |
| `d-kimuson/claude-code-viewer` | GoogleAgentSkills | ClaudeCode, PlaywrightCLI, JEV | SANDBOX_ONLY | Authentication, host binding, session isolation and terminal permissions must pass |
| `intel/auto-round` | ClaudeCode | KimiK3, JEV, GrokBot, ChatGPT | RESEARCH_ONLY | Reproducible model quality, calibration, latency, memory and hardware benchmark required |
| `D4Vinci/Scrapling` | GoogleAgentSkills | ClaudeCode, GrokBot, JEV | SANDBOX_ONLY | Network egress restrictions, redirect/DNS checks, rate limits and prompt-injection handling |
| `cyberchitta/scrapling-fetch-mcp` | GoogleAgentSkills | ClaudeCode, GrokBot, JEV | SANDBOX_ONLY | **Blocked** pending authentication, SSRF/private-network denial, DNS/redirect and resource-limit tests |
| `popiliadam/platinum-seo-engine` | ClaudeCode | GrokBot, JEV, ChatGPT | REFERENCE_ONLY | Separate marketing workspace only; AGPL-3.0 review; do not copy inspected MCP config as-is |

## Implementation status

- Nine entries from the ten supplied URLs were added to the existing external repository registry; `intel/auto-round` was already registered and its existing entry retained.
- Specialist routing rules were added for the new categories. The repository registry and routing changes are on this review branch, not on `main`.
- The federation audit and agent assignment audit passed on commit `6a585b8f649338fc877c245b33aa9dc811c6cfd4`. The broader AURELIA Assurance workflow was still running at the time of the latest status check.
- Physical runtime installation is explicitly not claimed. No upstream code was cloned, executed, vendored, or merged into AURELIA's capital/execution paths.
- No external repository may read production secrets, submit broker transactions, mutate LIVE_LOCK, authorize capital, or control the release gate. The existing live lock remains active and final execution authorization remains false.

## Release criteria

Before any candidate advances beyond its current mode:
1. Re-fetch the exact pinned commit and verify manifest/license file blob SHAs.
2. Generate an SBOM and transitive license/dependency report; run secret scan, SAST and dependency vulnerability scan.
3. Run component-specific security tests in an isolated, disposable environment with no broker credentials.
4. Require independent review, passing tests, documented rollback and explicit approval before any installation.
5. Keep third-party browser, MCP, shell, terminal, Git-write, and remote-control privileges outside the capital plane.

A successful repository-policy workflow validates metadata and policy invariants only. It does not certify upstream code security, runtime installation, production readiness, or live-trading eligibility.
