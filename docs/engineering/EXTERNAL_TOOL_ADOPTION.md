# External Tool Adoption Review — 2026-11-09

## Decision

[Certain] Only Ruff is adopted as a pinned development-only dependency. Two AURELIA-specific Claude Code skills are saved locally under `.claude/skills/`, following Anthropic's Agent Skills structure. The remaining repositories are assessed and assigned to existing agent roles as reference, research, sandbox, optional workstation tooling, or rejected sources.

The supplied Qwen Code URL appears four times; it is one project and one assessment. Qwen Code and Open Interpreter were already present in the larger external federation registry at older commits. Their current source snapshots are recorded in `config/external_tool_intake_2026-11-09.json`; no binary has been installed or run by this change.

## Repository decisions

| Repository | Current decision | Primary assignment | Constraint |
|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | Adopt format; maintain local AURELIA skills | ClaudeCode; GoogleAgentSkills reviews | No bulk import or unreviewed executable skills |
| [wddadk/Offensive-OSINT-Tools](https://github.com/wddadk/Offensive-OSINT-Tools) | Reference only; no runtime install | GoogleAgentSkills, JEV | Use only authorized security review; no third-party OSINT collection |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | Sandbox evaluation only; no production install | ClaudeCode, GoogleAgentSkills, JEV | Arbitrary code/command execution; no secrets or production sessions |
| [ivopetiz/algotrading](https://github.com/ivopetiz/algotrading) | Research reference; reject engine integration | KimiK3, GrokBot, JEV | Crypto exchange framework does not establish Deriv synthetic-index/options correctness |
| [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | Optional secondary coding harness | ClaudeCode, JEV, GoogleAgentSkills | Apache-2.0; isolated workstation only; no production secrets or self-approval |
| [rndinfosecguy/Scavenger](https://github.com/rndinfosecguy/Scavenger) | Reject execution | GoogleAgentSkills, JEV | Scrapes paste sites for exposed credentials/secrets; do not run or ingest findings |
| [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw) | Sandbox reference only | GrokBot, ClaudeCode, GoogleAgentSkills | Duplicates agent orchestration and tools; process-level privileges are not production isolation |
| [Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code) | Reject install | GoogleAgentSkills, ClaudeCode | Current LICENSE and pyproject.toml declare AGPL-3.0-only; adds another provider/key-routing layer |
| [remorses/playwriter](https://github.com/remorses/playwriter) | Isolated browser sandbox only | PlaywrightCLI, GoogleAgentSkills | Can control an existing Chrome profile; never use a signed-in production profile |
| [sham00n/buster](https://github.com/sham00n/buster) | Reject runtime install | GoogleAgentSkills, JEV | Privacy-sensitive email/social OSINT; unrelated to trading evidence |
| [astral-sh/ruff](https://github.com/astral-sh/ruff) | Adopt as dev extra | ClaudeCode, JEV, Dev | Pinned `ruff==0.17.4`; not in runtime image |
| [astral-sh/ruff-vscode](https://github.com/astral-sh/ruff-vscode) | Optional workstation extension | ClaudeCode, Dev | Not a runtime dependency |
| [ruffle-rs/ruffle-android](https://github.com/ruffle-rs/ruffle-android) | Reject name collision | ClaudeCode, JEV | Android Flash emulator frontend, not Astral Ruff |
| [astral-sh/ruff-action](https://github.com/astral-sh/ruff-action) | Defer Action adoption | ClaudeCode, GoogleAgentSkills, JEV | Use CLI first; action must be pinned to immutable full SHA before use |
| [ghostty-org/ghostty](https://github.com/ghostty-org/ghostty) | Optional workstation terminal | Dev, ClaudeCode | Not installed on runtime hosts |
| [ghostfolio/ghostfolio](https://github.com/ghostfolio/ghostfolio) | Reject embedding | KimiK3, ClaudeCode, JEV | Separate portfolio product; current source license is AGPL-3.0-only |
| [HowToFind-bot/osint-tools](https://github.com/HowToFind-bot/osint-tools) | Catalogue/reference only | GoogleAgentSkills, JEV | Not a single dependency; individual tools require separate license/security review |

## Agent allocation

Use the existing canonical matrices:
- `config/agent_tool_skill_assignment.json`
- `config/agent_capability_matrix.json`
- `config/agent_capability_boundary.json`
- `config/external_repo_federation.json`

Task ownership is: ClaudeCode implements; JEV independently validates schemas/tests/release evidence; KimiK3 handles quantitative research only; GrokBot coordinates research/dependency analysis; GoogleAgentSkills reviews supply-chain/agent security; PlaywrightCLI handles isolated browser tests; GLM inspects visual/document evidence; ChatGPT supervises and cross-checks in the active session. DeepSeek Harness and Hermes are proposed reviewer/operations roles but are **not connected in this session**; no task is claimed as run by them. Dev remains NOT_CONNECTED until a user-controlled host is attached and its identity is verified.

## Safety boundaries

No external agent, tool, skill, browser, or repository receives capital authority. No third-party code is copied into broker, risk, capital, execution, or reconciliation paths. No production secret values are read, printed, committed, or routed through an external model gateway. No authenticated browser profile is handed to Playwriter or Open Interpreter. No tool that discovers exposed third-party credentials is executed.

A repository's SHA pin is a repeatable reference, not an attestation that its code is safe or compatible. Runtime installation requires a separate dependency/SBOM/license/threat-model review, isolated tests, and a human approval.

## What this change actually installs

- AURELIA-authored Claude Code skills under `.claude/skills/`.
- Claude Code and universal agent project instructions updated to point at the new skills and intake contract.
- Ruff added to `pyproject.toml` as the optional `dev` dependency `ruff==0.17.4`.

It does **not** install Claude Code, Qwen Code, Open Interpreter, QwenPaw, Hermes, DeepSeek, Playwriter, Ghostty, a portfolio UI, or any OSINT tools on a machine. It does not alter the production Docker image or `LIVE_LOCK`. Claude Code discovers repository-local instructions when the user opens this repository; it is not a change to the user's remote Claude account.
