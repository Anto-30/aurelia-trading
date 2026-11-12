# Incremental External Repository Review — 2026-11-11

## Decision

All 11 requested repositories are recorded with immutable commit snapshots and task-scoped assignments. Open Interpreter and Scavenger were already present in the 2026-11-09 intake, so this adds 9 new unique repositories and refreshes two existing source pins.

No upstream executable, package, agent, plugin, hook or runtime service was installed or executed. This is first-pass triage from GitHub metadata, README files, available licence files and selected documentation. Full source review, SBOM, dependency audit, static/dynamic analysis, isolated tests and host compatibility remain outstanding.

## Repository decisions

| Repository | Licence | Disposition | Assigned roles | Assessment |
|---|---|---|---|---|
| [janestreet/agent_skills](https://github.com/janestreet/agent_skills) | MIT reported by metadata; LICENSE not found | Reference only | ClaudeCode, ChatGPT, GLM | One Socratic tutor skill; no AURELIA engineering fit. |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | Apache-2.0 | Sandbox evaluation only | ClaudeCode, GoogleAgentSkills, JEV, PlaywrightCLI | Command-execution agent harness; disposable sandbox only. |
| [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | MIT | Defer install; research-only | GrokBot, ChatGPT, GoogleAgentSkills, JEV | Recent-source research; broad Bash/Read/Write and optional API/browser credentials require isolation. |
| [huamidev/GestaltX](https://github.com/huamidev/GestaltX) | GPL-3.0 | Reject AURELIA adoption | GoogleAgentSkills, JEV, GLM | iOS MobileGestalt/device feature-flag editor; unrelated to trading. |
| [lxlynx/ops-toolkit](https://github.com/lxlynx/ops-toolkit) | MIT | Candidate after script audit | ClaudeCode, Dev, JEV, GoogleAgentSkills | Small Bash/Python host scripts; inspect each before copying or running. |
| [lxlynx/model-router](https://github.com/lxlynx/model-router) | MIT | Research candidate; no gateway install | GrokBot, ClaudeCode, GoogleAgentSkills, JEV | Explainable first-match routing; compare with existing gateway and avoid duplicate authority. |
| [rndinfosecguy/Scavenger](https://github.com/rndinfosecguy/Scavenger) | MIT | Reject execution; prior rejection reaffirmed | GoogleAgentSkills, JEV | Explicitly collects email/password pairs and exposed API credentials from paste sites. |
| [opensandbox-group/OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) | Apache-2.0 | Priority architecture evaluation; no deployment | ClaudeCode, GoogleAgentSkills, JEV, Dev, PlaywrightCLI | Candidate isolation substrate; review privileges, egress, image provenance, vault and escape boundaries. |
| [bhavsec/reconspider](https://github.com/bhavsec/reconspider) | GPL-3.0 | Reject install | GoogleAgentSkills, JEV | Legacy broad OSINT tool; privileged setup.py installer and third-party API keys; last surfaced commit 2021-08-19. |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | MIT | Selective skill review; no bulk install | ClaudeCode, GoogleAgentSkills, JEV, GrokBot | README claims 71 agents and 314 skills plus hooks/memory; review individual components only. |
| [lxlynx/eval-harness](https://github.com/lxlynx/eval-harness) | MIT | Candidate offline agent evaluation | KimiK3, GrokBot, ClaudeCode, JEV, ChatGPT | Deterministic scoring; README diff claim conflicts with TODO roadmap, so verify implementation. |

## Agent allocation

- **ClaudeCode — primary implementer:** inspect source trees, dependencies, tests and install scripts; evaluate OpenSandbox; assess ops-toolkit/model-router/eval-harness; selectively inspect ECC skills. Isolated workspace, no secrets.
- **JEV — independent validator:** verify pins, licences, SBOMs, dependency/test evidence and permission boundaries. Assignment does not prove a JEV runtime is connected.
- **GoogleAgentSkills — security reviewer:** threat-model OpenSandbox/Open Interpreter; inspect ECC hooks and last30days egress; preserve rejection of Scavenger and ReconSpider.
- **GrokBot — adversarial design/research:** compare model-router with existing gateway; challenge fallback/data-egress design; assess last30days source provenance.
- **KimiK3 — quantitative evaluation:** inspect eval-harness determinism using synthetic agent/prompt cases. It is not a financial backtester.
- **PlaywrightCLI — browser QA:** disposable sandbox and synthetic logins only; never a signed-in production profile.
- **Dev — workstation operator:** test ops scripts and sandbox deployment only after device connection and identity verification; currently NOT_CONNECTED.
- **GLM — document inspection:** architecture diagrams, licences and evidence extracts; no execution privileges.
- **ChatGPT — supervisory reviewer:** maintain intake, compare evidence and verify assignments; current-session role, not a persistent worker.
- **DeepSeek Harness and Hermes:** NOT_CONNECTED; no work is represented as executed by them.
- **AURELIA:** sole canonical policy/risk/capital/execution authority. No external source receives secrets, broker access, order authority, capital authority, LIVE_LOCK mutation or production deployment authority.

## Installation gates

1. Inspect exact source trees at pinned SHAs, manifests, install scripts, workflows, hooks and network calls.
2. Generate SBOM; run licence, vulnerability, secret, static and malware checks in an isolated workspace.
3. For execution-capable tools, test filesystem escape, network egress, credential leakage, process escalation and prompt injection.
4. Test compatibility without importing code into broker, risk, capital, execution or reconciliation paths.
5. Require independent review and exact test evidence before a separate PR proposes any dependency or skill installation.

OpenSandbox Credential Vault documentation requires enforced dns+nft egress and explicit outbound allowlists. This is not authorization to inject AURELIA/Deriv credentials.

## Provenance

Machine-readable record: config/external_tool_intake_2026-11-11.json. The 2026-11-09 intake remains the parent record. Commit pins identify snapshots, not trust. No LIVE_LOCK, production dependency, runtime Docker, broker, capital-plane or release-authorization change is included.
