# AURELIA Agent Skills Federation — 2026-10-04

## Purpose

AURELIA now has a pinned, cross-agent engineering capability registry covering Claude Code, Kimi K3/Kimi Code, Grok Bot, Google Agent Skills, GLM Skills, and Playwright CLI.

The registry is a coordination and provenance layer. It does not install external software into production and it does not grant capital authority.

## Source set

| Ecosystem | Source | Pinned commit | Trust | Intended AURELIA use |
|---|---|---|---|---|
| Claude Agent Skills | anthropics/skills | 8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4 | Official | skills, web testing, documents, agent workflows |
| Claude Code Plugins | anthropics/claude-plugins-official | d182ca456ca09d31d139f7d3818d1d333b103cce | Official | plugin structure, agents, hooks, MCP |
| Kimi Code | MoonshotAI/kimi-code | 21406fb4c805cc8c715e6d1f16ad3fb5f25f4fe3 | Official | plugins, skills, agents, MCP |
| Kimi CLI | MoonshotAI/kimi-cli | 9ab1286b8fe4e6bcd116949a27ce5e0ac3389c82 | Official | portable Agent Skills format |
| Grok Plugin Marketplace | xai-org/plugin-marketplace | 77a16ec85ded1c3b133f686bd2e1bea36090e124 | Official | plugins, skills, hooks, MCP, LSP, trust model |
| Awesome Grok Bot | ZeroPointRepo/awesome-grok-bot | fa6ef78f4535cd3fb460925b7b6c3336103fbc3e | Community | ecosystem discovery only |
| Google Agent Skills | google/skills | 1d77046ad3670d62227f50a8f53286f6c6cde08b | Official | multi-agent security, agent gateway, cloud architecture |
| GLM Skills | zai-org/GLM-skills | 2ecd31c37e75671a4767342ba3a68a84c8f1b848 | Official | OCR, multimodal evidence inspection, document analysis |
| Playwright CLI | microsoft/playwright-cli | b85c7a736bb473bf55b584e54a09ffa698d6d871 | Official | browser E2E, tracing, network/session verification |

## Federation rule

One architecture, one capital plane, one release lock, multiple advisory/engineering agents.

The external ecosystems may contribute:
- engineering patterns;
- research techniques;
- test-generation strategies;
- browser automation;
- multimodal evidence inspection;
- deployment/security design;
- plugin and skill packaging.

They may not:
- submit capital-moving orders;
- read, print, or persist secrets;
- flip `FINAL_EXECUTION_AUTHORIZATION`;
- disable `LIVE_LOCK`;
- bypass Risk Warden or Execution Firewall;
- reinterpret simulation as broker or production evidence.

## Repair protocol

Every defect follows:

`inspect -> reproduce -> isolate -> smallest fix -> deterministic test -> evidence capture -> state reconciliation -> certification re-check`

No second trading engine is created. No historical source is fabricated. No external plugin is allowed to mutate capital state.

## Current certified evidence

The non-production 3,600-second control-path soak is certified as `SIMULATION_VERIFIED` for source commit `3389e630c9de05f14a05763a6456ad698aca7f81`.

It recorded:
- 3,601 seconds;
- 706 health checks;
- 3 controlled restarts;
- 0 health-check failures;
- live execution blocked;
- no authenticated Deriv session;
- no broker transaction;
- no real capital movement.

Evidence artifact: `reports/certification/SIMULATION_VERIFIED_NONPROD_3600S_2026-10-04.json`

## Outstanding external evidence

The federation does not remove genuine blockers:
- Railway production infrastructure;
- authenticated Deriv session with authorized secrets;
- real transaction lifecycle and reconciliation;
- production worker soak;
- prospective OOS/calibration/economics;
- independent security/bypass audit.

The federation exists to accelerate and cross-check those gates, not to weaken them.
