# Third-Party Skill Intake and Provenance

Status: curated, repository-local Claude Code skill files added on branch `integration/curated-claude-skills-20261114`. These are prompt/document assets only. They are not executable code, MCP servers, plugins, hooks, or production integrations.

## Accepted for controlled repository-local use

| Local skill | Upstream | Pinned upstream revision | Source file | License | Scope |
|---|---|---|---|---|---|
| `thinking-pre-mortem` | [tjboudreaux/cc-thinking-skills](https://github.com/tjboudreaux/cc-thinking-skills) | `7b8fece345dfaa11773be7152ccd194589cb5437` | `skills/thinking-pre-mortem/SKILL.md` | MIT | Pre-release risk analysis; advisory only |
| `llm-trading-agent-security` | [affaan-m/ECC](https://github.com/affaan-m/ECC) | `d2ef2680594f9a17526a6e1a2e18b3d242c5d17b` | `skills/llm-trading-agent-security/SKILL.md` | MIT | Security-review checklist adapted with AURELIA-specific restrictions |

The two upstream projects' MIT license notices must be retained if substantial source text is redistributed. The AURELIA adaptations include local guardrails and are not upstream-certified.

## Explicitly not installed

- NVIDIA `NVIDIA/skills`: repository reviewed as a broad hardware/software skill catalogue. Current DOCA-focused examples do not materially improve AURELIA's Deriv trading workflow. Reconsider only a specific, relevant CUDA/robotics/vision/ontology skill after matching it to a real project requirement.
- `oss-invisible/dots`: not approved. Its project description advertises anti-bot evasion; no place in AURELIA's trusted workflow.
- `memodb-io/Acontext`: not approved. Repository is archived and its README states it is no longer maintained.
- Robotics/edge-AI repositories (`JacopoPan/aerial-autonomy-stack`, `stereolabs/zed-sdk`, `stereolabs/zed-ros-wrapper`, `stereolabs/zed-ros2-wrapper`, `alexandrepedrosaai/Edge-AI-APP`): not installed; no demonstrated AURELIA requirement.
- General catalogues and IDEs (`awesome-*`, `zed-industries/zed`, `zed-industries/extensions`, `CodePilot`, `suparagent`, `awesome-egm`, `auto-ontology-mcp`, `plannotator`, and the remaining skill collections): reference-only pending individual skill selection, license review, provenance pinning, and content/security review.
- `anthropics/claude-plugins-official`: official upstream source, but no plugin or hook was installed. Plugin execution requires a separate least-privilege review and explicit approval.

## Installation and synchronization model

These files live under `.claude/skills/<skill-name>/SKILL.md` in the canonical repository. They become available to a Claude Code checkout only after the branch is reviewed and merged, then pulled into that checkout. This GitHub operation does not install anything on a phone, desktop, Claude account, or remote agent runtime.

No install script, package manager, MCP server, plugin, hook, or external agent process was executed by this intake.

## AURELIA trust policy

- Third-party skills are advisory only and have no capital, broker, secret, or deployment authority.
- External code execution is denied by default; community sources remain research-only until separately reviewed.
- No agent or skill may alter `config/LIVE_LOCK.yaml`, bypass the deterministic risk engine, or authorize live execution.
- Preserve the current live lock and VERIFY_ONLY posture. This intake does not change execution settings.
- Pin every source revision. Re-review on upstream updates; never auto-update unreviewed skill content.


## Related intake work

The broader user-supplied repository registry and intake record are proposed separately in [PR #329](https://github.com/Anto-30/aurelia-trading/pull/329). That PR is still open and currently mixes registry/documentation changes with security-sensitive workflow edits. Its head is not based on the current PR #292 security branch (the refs diverge). Do not treat the registry as merged or synchronized to `main`, and do not merge PR #329 in its current form. The skill files in this PR are independently limited to advisory text and do not depend on merging #329.
