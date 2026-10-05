# gstack / Flow-Kit Workflow Federation — 2026-10-05

AURELIA federates seven external workflow sources for engineering intelligence. They are not additional trading engines.

## Sources

| Repository | Pinned commit | Role |
|---|---|---|
| garrytan/gstack | 10315cf44d1ea13e3ae4821841873afbf7807935 | Engineering workflow/toolchain |
| rihebty/flow-kit | 9b5dda7206ae841230f118348d660ad8d0ae2830 | Workflow reference |
| thanh-abaii/gstack-windows-port | 26937232ba2141c6bcf6ffdd8e0822163b475d63 | Windows toolchain reference |
| lucas-flatwhite/gstack-ko | 18bacc475cb5f7bf57647f4fbb647415c65c2303 | Localized skill reference |
| mr-daedalium/ostack-saas | a67256db4451f2d085370cfc36ebe091211b8e7b | Alternative agent-team workflow reference |
| Ahacad/gstack | f873a4d051b16a6652a3463cd1cd060dde86a24b | Claude Code plugin wrapper |
| loperanger7/gstack-auto | 17bf2a025c175b899e7d30be1ab4e658fd4ae04f | Sandbox parallel-engineering orchestration |

## Agent routing

ClaudeCode is the primary implementation/review consumer. GrokBot is assigned the workflow orchestration, adversarial-review and system-level reasoning subset.

The intended AURELIA use is:

1. gstack — planning, engineering review, QA, security and browser verification.
2. flow-kit — flow/orchestration patterns.
3. Windows port — Windows compatibility and PowerShell-specific engineering.
4. gstack-ko — localized skill/reference material.
5. ostack — alternative engineering-team and review patterns.
6. Ahacad/gstack — Claude Code plugin packaging/discovery patterns.
7. gstack-auto — isolated sandbox experiments for parallel engineering and iterative scoring.

## Important distinction

The presence of a workflow tool does not make its output authoritative. AURELIA's deterministic controls remain authoritative.

These sources cannot:

- authorize capital;
- submit or modify broker orders;
- change LIVE_LOCK;
- change FINAL_EXECUTION_AUTHORIZATION;
- read production secrets;
- qualify a trading strategy;
- override Risk Warden;
- override Execution Firewall;
- convert research evidence into live authorization.

gstack-auto is specifically sandbox-only because its purpose is autonomous parallel implementation and winner selection. Its scoring is software-engineering evidence, not trading-performance evidence.

## Upstream observation

The current upstream gstack repository describes a skill suite spanning planning, review, QA, browser interaction, security, shipping and other engineering workflows. AURELIA treats those capabilities as engineering assistance, not trading authority.

## Provenance

All pins and routing assignments are recorded in:

- `config/external_repo_federation.json`
- `config/agent_skill_federation.json`
- `config/gstack_workflow_sync.json`

