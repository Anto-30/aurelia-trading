# Curated third-party agent capabilities

This folder records selected third-party sources imported into AURELIA. External repositories remain advisory, pinned and non-authoritative. No installer scripts, arbitrary executables, model gateways, plugin runtimes, or credentials are imported.

The MIT-licensed finance skills were selectively copied as Markdown only into the canonical `skills/` tree and mirrored into Claude Code (`.claude/skills`), Grok (`.grok/skills`) and Agent Skills / DeepSeek Harness / Codex project roots (`.agents/skills`). The copied set is limited to statistics, performance metrics, return calculations and operational risk. Upstream scripts were not imported or run.

Source: https://github.com/JoelLewis/finance_skills
Pinned commit: `5c498eacf7057e31238c4c5a8012a1afe9ec7c8a`
License notice: `licenses/finance_skills-MIT.txt`

These project-local files become available when the corresponding agent opens this repository. This does not install skills into a separate hosted Claude account, user-global Claude home, or an unconnected DeepSeek/Hermes runtime.

## Project-local Claude agents

AURELIA also defines four repository-specific Claude Code agents under `.claude/agents/` for security auditing, secrets hygiene, quantitative research, and runtime reliability. These are original AURELIA-specific role contracts adapted from selected MIT-licensed Agency agent concepts; they are not copied upstream installers or runtime executors. The `agency-agents` MIT notice is at `licenses/agency-agents-MIT.txt`.

The finance skill documents are available in Claude Code, DSH/Codex-style project skill roots, and Grok's project skill root. All are advisory and do not grant account, secret, execution, deployment, or capital permissions.

## Sources deliberately not installed

The other user-supplied agent frameworks, Dify platform/plugins/sandboxes, Flutter SDK, desktop agent installer, and China-market skill pack remain pinned references only. Projects with no declared license or GitHub `NOASSERTION` metadata were not copied. Multi-agent runtimes and Dify code-execution infrastructure were not installed because they would create another tool execution plane without an approved isolated runtime and threat model.
