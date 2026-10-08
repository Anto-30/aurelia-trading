# AURELIA Claude Primary Brain — Design Specification

**Status:** Draft for user review
**Base:** current `main` branch
**Date:** 2026-10-08

## 1. Goal

Make Claude the primary intelligence-plane brain and system orchestrator for AURELIA while preserving AURELIA's deterministic capital plane as the sole authority capable of authorizing capital movement.

## 2. Non-negotiable boundaries

Claude, other LLMs, external repositories, browser agents, research agents, and orchestration services remain outside capital authority.

No intelligence-plane component may:
- disable or mutate LIVE_LOCK to authorize itself;
- set FINAL_EXECUTION_AUTHORIZATION directly;
- bypass Risk Warden, Execution Firewall, exposure checks, reconciliation, idempotency, fencing, broker verification, or kill switch;
- fabricate or promote strategy qualification, OOS, calibration, economics, or readiness evidence;
- submit an order directly to Deriv;
- read or expose production secrets outside the approved secret interface.

AURELIA's CapitalPlaneExecutor and release gate remain the final deterministic authority.

## 3. Intelligence hierarchy

Claude is the primary brain and coordinator.

Claude responsibilities:
- system-level task decomposition and prioritization;
- cross-agent orchestration;
- research-plan generation;
- synthesis of specialist findings;
- challenge/review of competing conclusions;
- engineering coordination;
- evidence-lineage-aware recommendations;
- persistent project/context coordination.

Specialists operate under Claude's orchestration:
- Grok: adversarial/challenger reasoning and independent review;
- Qwen: secondary reasoning, coding, research and large-context analysis;
- Dev/Claude Code: implementation and verification;
- quantitative agents: strategy research, OOS, calibration and statistical validation;
- market agents: regime, structure, microstructure and macro/news;
- security/audit agents: independent control and provenance verification.

AURELIA itself remains the capital-control authority, not an LLM.

## 4. Persistent orchestration

The existing persistent federation is extended rather than replaced.

The system maintains:
- agent registry and capability matrix;
- task queue with priority and ownership;
- append-only federation journal;
- leases and heartbeats;
- stale-agent detection;
- correlation IDs and duplicate suppression;
- evidence provenance;
- restart/recovery state;
- agent performance/evaluation ledger;
- Claude orchestration state.

Claude becomes the root orchestrator identity for intelligence-plane tasks.

If Claude is unavailable, the system must fail safe for capital operations. A configured fallback brain may continue bounded research only; it cannot silently become capital authority.

## 5. Model routing

Claude is the default/root route for system-level orchestration.

Specialist routing remains capability-based. Claude may delegate to Grok, Qwen, Dev, research agents, or other registered agents. Delegation results must include source/model identity, task ID, timestamps, evidence references, and outcome status.

Model-router abstention remains enabled. An unavailable or unverified model cannot be represented as available.

## 6. Evidence flow

`Claude -> specialists -> evidence -> deterministic validation -> release gate`

LLM conclusions are recommendations, not authorization.

Evidence must be bound to:
- source commit;
- configuration hash;
- runtime identity where applicable;
- evidence hash/provenance;
- expiration/freshness;
- originating agent/model;
- task/correlation ID.

Only validated evidence can influence readiness.

## 7. Failure handling

If Claude becomes unavailable:
- capital execution remains fail-closed;
- no automatic elevation of another LLM to capital authority;
- active research tasks become resumable/reassignable;
- stale Claude leases are detected;
- unfinished tasks are recovered from the persistent journal;
- deterministic safety services continue independently.

If any critical capital-plane component is UNKNOWN, stale, unauthenticated, unreconciled, or invalid, new exposure remains blocked.

## 8. Agent leaderboard

The existing evidence-backed leaderboard may evaluate Claude and all subordinate agents using:
- cumulative points;
- decayed points;
- success rate;
- evidence quality;
- penalties;
- evaluations;
- current rank;
- exact supporting evidence.

Leaderboard scores must never grant capital authority.

## 9. Deployment and security

Claude orchestration configuration belongs to the intelligence plane. Production credentials remain in the protected runtime secret store. No secret is committed to Git or passed through agent prompts.

External repositories remain sandbox/reference/toolchain inputs unless explicitly reviewed. They cannot alter the capital boundary.

## 10. Testing requirements

Before deployment, tests must prove:
1. Claude is selected as the primary orchestrator.
2. Specialist delegation works and records provenance.
3. Claude cannot directly authorize capital.
4. Fallback-agent activation cannot authorize capital.
5. Missing/unavailable Claude causes safe degradation.
6. Restart recovers pending orchestration tasks.
7. Duplicate task/message delivery is suppressed.
8. Evidence retains model, task and provenance lineage.
9. Unknown/stale capital evidence blocks execution.
10. Existing probability policy remains 0.55–0.75 with no clipping.
11. Existing Risk Warden, Execution Firewall, reconciliation, idempotency and kill-switch invariants remain enforced.
12. Existing live-release evidence requirements remain unchanged.

## 11. Success criteria

The change is complete only when:
- Claude is demonstrably the primary intelligence orchestrator in runtime configuration;
- all agents are correctly subordinated/routed by capability;
- persistent orchestration survives restart;
- fresh automated tests pass;
- current-source evidence is generated;
- capital authority remains exclusively deterministic;
- the live release gate still requires genuine authenticated Deriv, strategy, calibration, economics, production-runtime and soak evidence.

Changing the Claude configuration alone does not authorize live trading.

## 12. Continuous delegation, hunting and execution

Claude's orchestration loop is intended to be continuous rather than a one-shot planner. It may continuously create, prioritize, delegate, monitor, retry, reassign and close intelligence-plane work across the registered agent federation.

The continuous loop includes three distinct lanes:
- **Hunt:** continuously search for new strategy hypotheses, market regimes, symbols, features, execution improvements and external research. Every candidate enters evidence-backed validation and may be rejected.
- **Operate:** continuously monitor approved runtime components, market data, broker/session health, risk state, reconciliation, agent health and evidence freshness.
- **Execute:** continuously evaluate executable opportunities and submit execution intents to AURELIA's deterministic capital plane. Claude and subordinate agents may propose or request execution, but only the deterministic release/risk/execution gates can authorize a real order.

Continuous execution must never mean unconditional trading. When a strategy is unqualified, probability is outside 0.55–0.75, evidence is stale/invalid, balance is insufficient, broker state is UNKNOWN, reconciliation fails, a safety gate trips, or LIVE_LOCK/release authorization is false, the execution lane must remain blocked while hunting and research continue.

Claude may delegate work to all registered agents according to capability, health, trust/evidence score, workload, latency, cost and task criticality. Agents may spawn bounded sub-tasks only when their registry permissions allow it. Every delegation has an owner, deadline/lease, correlation ID, provenance and completion state.

The scheduler must support persistent recurring jobs for strategy hunting, validation campaigns, news/macro monitoring, market scanning, calibration, execution surveillance, post-trade analysis, agent evaluation and system-health checks. Recurring work must be idempotent and recoverable after restart.

A strategy that passes all deterministic qualification and release requirements may be made eligible for execution by AURELIA. Claude does not promote it directly. Once eligible, the continuous execution loop may evaluate new opportunities without requiring a human prompt for every trade, subject to the existing deterministic capital controls and configured risk limits.

No continuous loop may convert a research hypothesis into live capital exposure merely because an LLM believes it is profitable. The transition remains evidence-driven and deterministic.

## 13. Operational objective

The desired operating model is:

Claude -> continuous planner -> capability scheduler -> all eligible agents -> research/hunt/evidence -> deterministic validation -> qualified strategy registry -> market opportunity evaluation -> Risk Warden + Execution Firewall -> CapitalPlaneExecutor -> Deriv -> reconciliation -> feedback -> Claude

This is a 24/7 autonomous operating loop, not a permission for unrestricted autonomous trading. Capital movement remains gated at every iteration.
