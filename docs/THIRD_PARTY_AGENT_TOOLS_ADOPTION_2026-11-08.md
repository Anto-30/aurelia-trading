# Third-party agent and skills intake — 2026-11-08

## Decision summary

This is a **curated project-level integration**, not a wholesale installation of 22 repositories.

- 22 supplied repositories were recorded with the observed default branch, current commit SHA, GitHub license metadata, adoption mode, and a reasoned disposition.
- 19 repositories were newly added to the AURELIA external-repository registry; three existing entries (`MichengAI/dsh-agency-agents`, `jnMetaCode/agency-agents-zh`, and `langgenius/dify`) had their commit pins refreshed.
- Four MIT-licensed `JoelLewis/finance_skills` Markdown skills were imported into `skills/`, mirrored to `.claude/skills/`, `.grok/skills/`, and `.agents/skills/`. Upstream scripts and automation were not imported.
- Four AURELIA-specific Claude project agents were added under `.claude/agents/`. They are project-scoped prompts, not a running Claude or Hermes service.
- The project-local `.agents/skills/` mirror is the DSH/portable Agent Skills surface. This does not establish a connected DSH runtime.
- No upstream installer, shell script, code-execution service, model gateway, Dify runtime, Flutter SDK, or desktop installer was run.
- Nothing in this integration can access production credentials, change AURELIA's release lock, submit broker requests, or authorize capital.

## Curated components actually staged

**Finance research skills** from `JoelLewis/finance_skills` at `5c498eacf7057e31238c4c5a8012a1afe9ec7c8a` (MIT):
- `research-statistics-fundamentals`
- `research-performance-metrics`
- `research-return-calculations`
- `security-operational-risk`

They are adapted for AURELIA and explicitly warn against carrying over securities-market, FIX, exchange-order-book, volume, or fee assumptions to Deriv synthetic indices without instrument-specific evidence.

**Claude Code project agents** adapted from selected role concepts in `msitarzewski/agency-agents` at `b859c515d813efcfc4755d3471dd9e7686c7706d` (MIT):
- `aurelia-security-auditor`
- `aurelia-secrets-hygiene-engineer`
- `aurelia-quantitative-researcher`
- `aurelia-runtime-reliability-engineer`

The imported prompts are AURELIA-specific and maintain zero capital authority. The original MIT notices are preserved at `third_party/licenses/`.

## Repository intake and disposition

| Repository | Branch | Pinned commit | GitHub license metadata | Mode | Runtime action | Assessment |
|---|---|---|---|---|---|---|
| [`anomalyco/rune`](https://github.com/anomalyco/rune) | `dev` | `a7f276c3630f` | MIT | `REFERENCE_ONLY` | No runtime install | Native UI framework; no AURELIA runtime need identified. |
| [`MichengAI/dsh-agency-agents`](https://github.com/MichengAI/dsh-agency-agents) | `main` | `3612123844c6` | Apache-2.0 | `SANDBOX_ONLY` | No runtime install | Already registered; refresh pin only. Community DSH plugin, not an official DeepSeek product. |
| [`tanweai/pua`](https://github.com/tanweai/pua) | `main` | `e6e6cd237ad1` | UNDECLARED | `REFERENCE_ONLY` | No runtime install | No declared license; do not copy or install. High-pressure PIP-style prompt not adopted. |
| [`msitarzewski/agency-agents-app`](https://github.com/msitarzewski/agency-agents-app) | `main` | `dda50547cf79` | MIT | `REFERENCE_ONLY` | No runtime install | Desktop app only; no authorized end-user device connected, so not installed. |
| [`VRSEN/agency-swarm`](https://github.com/VRSEN/agency-swarm) | `main` | `1bec92f0fc6e` | MIT | `SANDBOX_ONLY` | No runtime install | Second orchestration runtime would duplicate AURELIA federation; not installed. |
| [`Anas-Khan93/ai-agency-agents`](https://github.com/Anas-Khan93/ai-agency-agents) | `main` | `1c06454211dc` | MIT | `REFERENCE_ONLY` | No runtime install | Overlaps the larger canonical agency-agents library; no duplicate prompt import. |
| [`jnMetaCode/agency-agents-zh`](https://github.com/jnMetaCode/agency-agents-zh) | `main` | `d160421bb2a4` | MIT | `REFERENCE_ONLY` | No runtime install | Already registered; refresh pin only. Chinese translations and China-specific roles are not required for Deriv runtime. |
| [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents) | `main` | `b859c515d813` | MIT | `REFERENCE_ONLY` | Selected Markdown only | Selected role prompts adapted to AURELIA-specific Claude subagents; upstream installers and full roster not run. |
| [`flutter/flutter`](https://github.com/flutter/flutter) | `master` | `acade0f6b532` | BSD-3-Clause | `REFERENCE_ONLY` | No runtime install | Full mobile SDK unrelated to current Python execution engine; not installed. |
| [`jwangkun/claude-for-financial-services-cn`](https://github.com/jwangkun/claude-for-financial-services-cn) | `main` | `d7585ca0033d` | Apache-2.0 | `REFERENCE_ONLY` | No runtime install | China A-share accounting/data-source specialization; not adopted for synthetic-index trading. |
| [`JoelLewis/finance_skills`](https://github.com/JoelLewis/finance_skills) | `main` | `5c498eacf705` | MIT | `RESEARCH_ONLY` | Selected Markdown only | Four Markdown-only skills imported into AURELIA/Claude/DSH project roots; upstream scripts excluded. |
| [`iblai/financial-services-agents`](https://github.com/iblai/financial-services-agents) | `main` | `6ea18f015b1e` | MIT | `SANDBOX_ONLY` | No runtime install | OpenClaw/NemoClaw orchestration config; not connected or installed. |
| [`yand/codex-financial-services`](https://github.com/yand/codex-financial-services) | `codex-adapter` | `da5b5e004c0a` | Apache-2.0 | `REFERENCE_ONLY` | No runtime install | Codex adapter includes generated skill resources; no Codex runtime/connector was installed. |
| [`langgenius/dify-sandbox`](https://github.com/langgenius/dify-sandbox) | `main` | `95578774d74e` | Apache-2.0 | `SANDBOX_ONLY` | No runtime install | Not deployed; any future use requires separate container/network/filesystem threat review. |
| [`junjiem/dify-plugin-repackaging`](https://github.com/junjiem/dify-plugin-repackaging) | `main` | `3ed1ddce2c39` | UNDECLARED | `REFERENCE_ONLY` | No runtime install | No declared license; packaging scripts not copied or executed. |
| [`langgenius/dify-official-plugins`](https://github.com/langgenius/dify-official-plugins) | `main` | `18663b9e723c` | Apache-2.0 | `SANDBOX_ONLY` | No runtime install | Large plugin catalogue; no plugins installed or activated. |
| [`YFGaia/dify-plus`](https://github.com/YFGaia/dify-plus) | `main` | `c48ecee4d7c3` | NOASSERTION | `REFERENCE_ONLY` | No runtime install | License not resolved by GitHub metadata; no code copied. |
| [`wwwzhouhui/dify-for-dsl`](https://github.com/wwwzhouhui/dify-for-dsl) | `main` | `d2670fa8ab69` | UNDECLARED | `REFERENCE_ONLY` | No runtime install | No declared license; workflow files not copied. |
| [`langgenius/dify-plugins`](https://github.com/langgenius/dify-plugins) | `main` | `2c640c41e3ae` | UNDECLARED | `REFERENCE_ONLY` | No runtime install | No declared license; reference only. |
| [`svcvit/Awesome-Dify-Workflow`](https://github.com/svcvit/Awesome-Dify-Workflow) | `main` | `e730ed3627e5` | MIT | `REFERENCE_ONLY` | No runtime install | MIT licensed but last pushed in March 2026; examples not ported to runtime. |
| [`BannyLon/DifyAIA`](https://github.com/BannyLon/DifyAIA) | `main` | `d6a600c7e396` | UNDECLARED | `REFERENCE_ONLY` | No runtime install | No declared license; workflow files not copied. |
| [`langgenius/dify`](https://github.com/langgenius/dify) | `main` | `30aa6fd15b5d` | NOASSERTION | `SANDBOX_ONLY` | No runtime install | Already registered; refresh pin only. Full Dify platform is not installed in the trading runtime. |

## Runtime and trust boundaries

AURELIA remains the sole capital plane. The new skills and Claude agents are advisory engineering/research capabilities only. Third-party repositories remain pinned in `config/external_repo_federation.json` and `config/agent_skill_federation.json`; assignments route work to ClaudeCode, KimiK3, GrokBot, GoogleAgentSkills, JEV and ChatGPT as applicable. They do not create new running agents.

Claude Code discovers the project-local roles under `.claude/agents/` and skills under `.claude/skills/`. DeepSeek Harness-compatible project skills are placed under `.agents/skills/`. A separate hosted Claude account, user-global Claude installation, Hermes daemon, DSH process, Codex runtime, desktop installation, or external connector has **not** been authenticated or installed by this repository change.

All full-repository security reviews remain pending unless explicitly narrowed to the Markdown content imported. Unlicensed and GitHub `NOASSERTION` sources are reference-only; no files were copied from them. Dify and its plugins/sandbox remain sandbox/reference sources, not deployed services.

## Verification requirements

CI must validate:
1. Every intake SHA is a 40-character pinned commit and every repository has a matching registry entry.
2. Each intake record has `capital_authority=false`.
3. The four new skill docs exist in all four project skill roots.
4. The four Claude project-agent definitions exist.
5. The skill inventory, plugin inventory, assignment registry, and capability matrix agree.
6. `config/LIVE_LOCK.yaml` remains disabled and final execution authorization remains false.

No live-trading readiness claim follows from this integration.
