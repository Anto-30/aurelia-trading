# AURELIA ChatGPT + Claude Code Dual-Primary Federation, Production Runtime, and Live-Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ChatGPT and Claude Code the co-primary intelligence brains for AURELIA, establish durable production orchestration, generate fresh authenticated Deriv evidence, complete genuine strategy/OOS/calibration/economics evidence, verify a $1 stake path against live broker constraints, and permit real execution only after every deterministic release control passes.

**Architecture:** ChatGPT and Claude Code are co-primary intelligence-plane controllers with clear role separation: ChatGPT owns system-level intent, prioritization, synthesis, and final intelligence-plane coordination; Claude Code owns implementation, repair, verification, and engineering execution. All other agents remain subordinate specialists. AURELIA's deterministic CapitalPlaneExecutor, Risk Warden, Execution Firewall, reconciliation, idempotency/fencing, kill switch, LIVE_LOCK, broker truth, and release gate remain the sole capital authority.

**Tech Stack:** Python, asyncio, existing AURELIA runtime/federation, Deriv WebSocket API, GitHub Actions, signed readiness attestations, persistent JSON/NDJSON state, existing test suite, Docker/self-hosted production worker.

**Spec:** `docs/superpowers/specs/2026-10-08-claude-primary-brain-design.md`

## Global Constraints

- Claude and ChatGPT are the co-primary intelligence brains; Qwen is never a primary brain, root orchestrator, or capital authority.
- Intelligence-plane agents may recommend, research, implement, and challenge; they cannot authorize capital, mutate LIVE_LOCK, set FINAL_EXECUTION_AUTHORIZATION, submit Deriv orders directly, or access production secrets outside the approved secret interface.
- AURELIA CapitalPlaneExecutor and the deterministic release gate remain the final authority for live capital movement.
- `MIN_TRADE_PROBABILITY=0.55` and `MAX_TRADE_PROBABILITY=0.75`; no clipping.
- Stale, invalid, drifted, or uncalibrated probability evidence is no-trade.
- Strategy qualification requires genuine OOS / positive expectancy evidence with at least 100 trades per Strategy×Symbol×Regime where the applicable qualification path requires it.
- Unknown broker state, stale balance, failed reconciliation, inactive safety controls, or missing attestations must fail closed.
- $1 is the target starting stake only where the selected Deriv contract/platform actually permits it; AURELIA must verify affordability and broker proposal constraints before submission.
- Account growth must not be implemented as unconditional martingale or stake escalation. Sizing changes require verified-balance thresholds, explicit risk limits, and deterministic approval.
- External repositories remain sandbox/reference/toolchain inputs and cannot become a second trading engine or gain capital authority.
- No production secret values are committed to Git or exposed in task output.
- No live order is permitted until fresh authenticated evidence and release-gate evidence authorize it.

## Review Focus

- Dual-primary routing must be deterministic and must never silently promote Qwen or another model into the root role; test explicit precedence and fallback behavior.
- Production liveness must reflect real worker heartbeats/leases, not roster registration or synthetic status; test restart and stale-worker recovery.
- Authenticated Deriv evidence must bind account identity, environment, currency, source SHA, config hash, runtime ID, freshness, and provenance; test mismatches and expiry.
- $1 stake verification must use the actual broker proposal for the selected symbol/contract and reject amounts that are unsupported or unaffordable; test minimum amount, insufficient balance, and contract-specific constraints.
- Release must fail closed on every capital-plane invariant and must record an auditable reason; test LIVE_LOCK false, stale balance, probability outside 0.55–0.75, reconciliation failure, and unknown broker outcome.

---

### Task 1: Make ChatGPT + Claude Code the explicit co-primary federation roots

**Files:**
- Modify: `config/model_federation.json` (create only if the implementation branch already contains the federated model registry from PR #52; otherwise extend the repository's current model/agent configuration file)
- Modify: `config/agent_capability_matrix.json`
- Modify: `runtime/intelligence/model_router.py`
- Modify: `runtime/continuous_runtime.py`
- Test: `tests/test_model_router.py`
- Test: `tests/test_intelligence_evolution.py`
- Test: new focused federation test under `tests/`

**Interfaces:**
- Consumes: current agent/model registry and persistent federation APIs.
- Produces: a root-routing decision that identifies ChatGPT and Claude Code as the only co-primary roots, while preserving subordinate specialist routing.

- [ ] **Step 1: Write failing tests** named `test_dual_primary_roots_are_chatgpt_and_claude_code`, `test_qwen_is_never_a_primary_root`, and `test_unknown_primary_model_abstains`.
- [ ] **Step 2: Run the focused tests and verify failure against current routing behavior.**
  Run: `pytest tests/test_model_router.py tests/test_intelligence_evolution.py -q`
  Expected: FAIL on at least one new dual-primary assertion.
- [ ] **Step 3: Implement the dual-primary routing contract.** Use explicit IDs for the ChatGPT/OpenAI root and Claude Code/Anthropic engineering root; do not infer primacy from model availability. Keep specialist delegation capability-based.
- [ ] **Step 4: Run the focused tests and verify PASS.**
- [ ] **Step 5: Commit** with `feat: establish chatgpt and claude code dual primary federation`.

### Task 2: Add persistent Claude/ChatGPT orchestration state and delegation recovery

**Files:**
- Modify: `runtime/agent_federation.py`
- Modify: `runtime/agent_workers.py`
- Modify: `runtime/agent_performance.py`
- Modify: `runtime/continuous_runtime.py`
- Test: new persistence/federation tests under `tests/`

**Interfaces:**
- Consumes: `PersistentAgentFederation.enqueue_task/claim_task/complete_task/recover_stale_tasks`, leases, heartbeats, performance ledger.
- Produces: durable root-orchestrator task ownership, recurring work records, recoverable delegation leases, and performance/evidence lineage.

- [ ] **Step 1: Write failing tests** for root-owned task creation, capability assignment, stale lease recovery after restart, duplicate suppression, and heartbeat-based liveness.
- [ ] **Step 2: Run the focused tests and verify failure.**
- [ ] **Step 3: Implement the minimum state needed to persist root ownership, task provenance, correlation IDs, lease expiry, and recurring-job metadata without creating a second execution engine.**
- [ ] **Step 4: Run the focused tests and verify PASS.**
- [ ] **Step 5: Commit** with `feat: persist dual-primary orchestration and recovery`.

### Task 3: Establish continuous Hunt / Operate / Execute scheduling

**Files:**
- Modify: `runtime/continuous_runtime.py`
- Modify: `runtime/autonomous_loop.py`
- Modify: `runtime/strategy/research_supervisor.py`
- Modify or create: recurring-job scheduler module following existing runtime patterns
- Test: focused continuous-runtime and scheduler tests

**Interfaces:**
- Consumes: persistent federation task queue, active agent leases, Deriv adapter, decision provider, CapitalPlaneExecutor.
- Produces: idempotent recurring Hunt, Operate, and Execute jobs with restart recovery.

- [ ] **Step 1: Write failing tests** proving each lane exists, recurring jobs are persisted, and a blocked Execute lane does not stop Hunt/Operate.
- [ ] **Step 2: Run tests to verify failure.**
- [ ] **Step 3: Implement the scheduler using existing federation primitives; do not move capital authority into the scheduler.**
- [ ] **Step 4: Run tests to verify PASS.**
- [ ] **Step 5: Commit** with `feat: add persistent 24x7 hunt operate execute scheduling`.

### Task 4: Verify and repair the deterministic capital boundary

**Files:**
- Modify only the existing capital-plane components required by failing tests, especially `runtime/broker/executor.py` and adjacent gate modules.
- Test: existing capital authorization/pre-submission tests plus focused new tests.

**Interfaces:**
- Consumes: `Decision`, `CapitalSnapshot`, account truth, probability gates, Risk Warden, Execution Firewall, reconciliation state, release state, fence/idempotency state.
- Produces: a deterministic boolean authorization decision and auditable reason codes; no LLM direct capital path.

- [ ] **Step 1: Add/extend failing tests** for all global constraints in Review Focus.
- [ ] **Step 2: Run the capital-boundary suite and verify failures identify only actual gaps.**
- [ ] **Step 3: Implement minimal repairs.**
- [ ] **Step 4: Run the full relevant assurance suite and verify PASS.**
- [ ] **Step 5: Commit** with `fix: harden deterministic capital release boundary`.

### Task 5: Implement verified $1 proposal and adaptive balance-growth sizing

**Files:**
- Locate and modify the existing stake/position sizing and proposal path rather than creating a separate execution path.
- Test: focused sizing/proposal tests.

**Interfaces:**
- Consumes: verified broker balance, active symbol/contract metadata, Deriv proposal response, configured risk limits, deterministic release context.
- Produces: requested stake, broker-confirmed minimum/maximum constraints, affordability result, and next-size decision.

- [ ] **Step 1: Write failing tests** for exact $1 request, unsupported-minimum rejection, insufficient-balance rejection, and threshold-based stake increases.
- [ ] **Step 2: Run tests and verify failure.**
- [ ] **Step 3: Implement sizing so $1 is the starting target; query broker proposal/contract constraints before approval; increase size only at verified balance thresholds and within risk limits.**
- [ ] **Step 4: Add a live-broker verification path that records the proposal response without submitting a trade; verify the result is bound to symbol, contract, currency, account, timestamp, and source/config hashes.**
- [ ] **Step 5: Run focused tests and verify PASS.**
- [ ] **Step 6: Commit** with `feat: add broker-verified one-dollar sizing path`.

### Task 6: Complete genuine strategy, OOS, calibration, and economics evidence

**Files:**
- Use the repository's existing strategy qualification, research, calibration, and evidence modules.
- Modify only existing pipelines needed to close actual gaps.
- Test: qualification/calibration/evidence suites plus generated evidence fixtures where appropriate.

**Interfaces:**
- Consumes: canonical Deriv market data, strategy candidates, OOS runs, probability predictions, calibration results, execution-cost estimates.
- Produces: provenance-bound evidence artifacts suitable for deterministic release evaluation.

- [ ] **Step 1: Enumerate current strategy candidates and their evidence state from the repository's release/qualification tooling; mark missing evidence explicitly.**
- [ ] **Step 2: Write failing tests for promotion of only complete evidence and rejection of missing/stale/economically invalid candidates.**
- [ ] **Step 3: Run the research qualification and calibration pipelines against current canonical datasets; do not substitute synthetic or invented results for production evidence.**
- [ ] **Step 4: Generate multi-day prospective OOS, calibration, and cost/economics evidence for every strategy/symbol/regime combination that is intended for live consideration.**
- [ ] **Step 5: Verify the minimum trade-count, expectancy, calibration, freshness, and cost conditions required by the existing release policy.**
- [ ] **Step 6: Commit evidence/reporting pipeline changes and generated non-secret provenance manifests with message `feat: close strategy qualification evidence gaps`.

### Task 7: Establish protected production runtime and authenticated Deriv evidence

**Files:**
- Modify only deployment/configuration scripts and observability checks required to make the current self-hosted worker operational.
- Test: deployment/config validation and readiness-attestation tests.

**Interfaces:**
- Consumes: protected production secret interface, current Git SHA, runtime/config hashes.
- Produces: fresh authenticated Deriv session evidence, verified account identity/currency/environment, worker runtime ID, live heartbeats, signed capability attestations, and a 3600-second authenticated runtime evidence artifact.

- [ ] **Step 1: Verify production-host connectivity and stop immediately if the authorized device is not actually connected to the Remote Desktop connector.**
- [ ] **Step 2: Install/start the current repository revision in VERIFY_ONLY mode first and prove health/readiness, worker heartbeats, federation activity, and authenticated Deriv session without submitting orders.**
- [ ] **Step 3: Verify `accounts()`/account binding, balance freshness, active symbols, and Deriv session identity using protected secrets without printing secret values.**
- [ ] **Step 4: Generate all required readiness attestations with exact source SHA, config hash, runtime ID, signing key, evidence hashes, and expiry.**
- [ ] **Step 5: Run the required 3600-second authenticated worker soak and verify restart/recovery, reconciliation, watchdog, and idempotency evidence.**
- [ ] **Step 6: Commit only repository-side deployment/verification changes; production secret values remain outside Git.**

### Task 8: Final deterministic release gate and live execution validation

**Files:**
- Modify only release/reporting code if actual evidence-path defects remain.
- Test: certification/release suite and live preflight tests.

**Interfaces:**
- Consumes: fresh production evidence, strategy/economics/calibration evidence, $1 broker proposal evidence, all deterministic safety controls.
- Produces: release decision and, only on success, authorization context for the existing CapitalPlaneExecutor.

- [ ] **Step 1: Run the complete assurance, certification, and release-closure suite against the current source SHA.**
- [ ] **Step 2: Confirm the release report has no unresolved blocking condition; explicitly verify all required capability attestations.**
- [ ] **Step 3: Re-read authoritative broker balance immediately before any first live intent and verify the $1 stake remains affordable.**
- [ ] **Step 4: Execute exactly one controlled real trade only if the deterministic release gate returns allowed and all broker confirmations are fresh; otherwise remain fail-closed and continue Hunt/Operate.**
- [ ] **Step 5: Reconcile broker state, ledger, idempotency record, contract status, and account balance after the trade; trip the circuit breaker on any unknown or unexplained outcome.**
- [ ] **Step 6: Verify continuous operation after the first trade and record the result in the agent-performance/evidence ledger.**
- [ ] **Step 7: Commit any final repository-side fixes with `release: certify production live execution path`.

## Definition of Done

- ChatGPT and Claude Code are demonstrably the only co-primary intelligence roots.
- Qwen is explicitly subordinate and cannot become a primary/fallback root.
- All registered agents have capability-routed tasks and real worker heartbeats in production.
- Hunt, Operate, and Execute loops persist across restart and remain fail-safe.
- Fresh authenticated Deriv evidence is bound to the exact deployed source/config/runtime.
- Genuine strategy OOS, calibration, and economics evidence satisfies existing qualification requirements.
- The $1 stake path is broker-verified and affordability-checked before execution.
- Deterministic risk, firewall, reconciliation, idempotency, fencing, kill switch, broker truth, and LIVE_LOCK invariants remain intact.
- Live trading occurs only after the release gate itself returns authorization and a broker-confirmed transaction is recorded.
