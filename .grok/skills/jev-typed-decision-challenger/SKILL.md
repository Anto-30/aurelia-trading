---
name: jev-typed-decision-challenger
description: High-speed typed advisory challenger for GrokBot using pinned JEV community tooling.
version: 1.0.0
---

# JEV → Grok typed challenger

JEV operates only in AURELIA's advisory/research plane. GrokBot owns orchestration and interpretation.

Boundary:
- capital authority: false
- live orders: forbidden
- deployment authority: false
- secret access: forbidden
- LIVE_LOCK mutation: forbidden
- Risk Warden / Execution Firewall bypass: forbidden

Pinned source:
- repository: charlesdove977/claude-x-jev
- commit: c8662b0550b2a999d1dbcfb148683615cf92636a

Input:
- decision_id
- strategy/version
- symbol/direction
- proposed probability
- regime/market context
- evidence identifiers
- control/risk state
- proposition to challenge

Output:
- verdict: CONSISTENT | CHALLENGE | ESCALATE
- confidence
- bounded reasons
- source_commit
- authority: ADVISORY_ONLY

A CONSISTENT result never authorizes capital. A CHALLENGE or ESCALATE result is advisory only. All capital decisions remain inside deterministic AURELIA gates.
