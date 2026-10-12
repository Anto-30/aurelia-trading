# Claude agent patterns for AURELIA

These are complementary workflow patterns, not seven mutually exclusive agent types.

| Pattern | Claude Code mechanism | AURELIA use |
| --- | --- | --- |
| Tool-using agent | Built-in tools and explicitly configured MCP integrations | Approved repository and system access with least privilege |
| Reusable workflow | Skills under .claude/skills | /aurelia-assurance for repeatable evidence-led assurance |
| Sequential workflow | Orchestrator delegates in dependency order | Inspect, propose fix, test, independent review |
| Parallel workflow | Independent subagents via Agent tool | Risk, strategy, and test/evidence reviews run concurrently |
| Router | Dispatch rules in instructions or application code | Route research, risk, tests, and deployment questions to specialists |
| Human approval | Permission prompts and protected branches/environments | Approval for consequential deployment or capital-affecting changes |
| Orchestrator | Main Claude Code session coordinating subagents | Coordinate work while preserving one engine and one release authority |

## Guardrails
- This is developer workflow support, not a new trading runtime or autonomous capital agent.
- Specialist agents are read-only by default. Changes remain subject to review.
- Never store secrets in agent markdown, skills, prompts, or committed configuration.
- Do not commit credentials in MCP configuration.
- Parallelize independent analysis, not conflicting edits to the same files.
- CI success, static configuration, and simulated trades do not independently prove live readiness.
- The Risk Warden, Execution Firewall, live lock, broker verification, ledger/reconciliation, and existing release authority remain authoritative.

## Upstream references
- Claude Code: https://github.com/anthropics/claude-code
- Anthropic skills: https://github.com/anthropics/skills
- Claude Code guidance: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more
