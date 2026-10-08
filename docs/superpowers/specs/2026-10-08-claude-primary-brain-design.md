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
