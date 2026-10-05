# AURELIA Repository-to-Agent Routing Policy

Effective 2026-10-05.

Every new external repository added to AURELIA must be classified and assigned to the agents best suited to use its intelligence or engineering capabilities.

## Mandatory admission

A repository is not considered federated merely because its URL appears in a prompt, issue, branch, or research note. The repository must have an entry in `config/external_repo_federation.json` with:

- `repo`
- `category`
- `domain`
- `assigned_agents`
- `mode`
- `source_url`
- `head_commit`

A capability entry in `config/agent_skill_federation.json` is additionally required when the repository is being consumed as a skill, plugin, or agent source.

The first agent in `assigned_agents` is the primary consumer. Remaining agents are supporting consumers.

## Routing logic

Trading and quantitative repositories route primarily to KimiK3, with GrokBot and ClaudeCode normally supporting.

Security and agent-gateway repositories route primarily to GoogleAgentSkills, with ClaudeCode/GrokBot review.

Browser, UI, desktop, and visual-verification repositories route primarily to PlaywrightCLI, with ClaudeCode supporting.

Document, OCR, and multimodal sources route primarily to GLM, with ClaudeCode supporting.

Agent orchestration, workflow, Hermes, and coordination sources route primarily to GrokBot, with ClaudeCode/KimiK3 supporting.

Deployment and cloud tooling route primarily to ClaudeCode, with GrokBot and PlaywrightCLI supporting where relevant.

General engineering libraries and coding-agent tooling route primarily to ClaudeCode.

The routing registry is deterministic and can be overridden only by a reviewed exception that records the reason, reviewer, and review date.

## Safety

Agent assignment determines who may consume a repository's intelligence. It does not grant capital authority.

No external repository or assigned agent may:
- authorize a trade;
- mutate LIVE_LOCK or FINAL_EXECUTION_AUTHORIZATION;
- access production secrets;
- submit broker transactions;
- qualify a trading strategy;
- override Risk Warden or Execution Firewall.

The repository federation remains subordinate to AURELIA's deterministic capital-plane controls.

## Operational rule

When a new repository is supplied, the intake process is:

1. identify category/domain;
2. select the highest-priority routing rule;
3. assign primary and supporting agents;
4. pin the source commit;
5. register the capability entry;
6. run routing assurance;
7. only then allow the repository into AURELIA's federated intelligence/tooling set.
