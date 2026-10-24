# Layer 6 Fail-Closed Risk Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, execution-neutral risk-veto gate and reproducible five-case matrix without creating a second capital authorization system.

**Architecture:** The gate consumes a validated risk snapshot and returns `risk_approved` plus a reason code. It defaults disabled, rejects malformed/unknown state, checks stake/exposure/daily loss, and denies results that exceed a synchronous elapsed-time budget. It performs no I/O and has no broker adapter; AURELIA's existing capital plane and LIVE_LOCK remain the only final execution authority.

**Tech Stack:** Python 3.11+, dataclasses, standard library unittest, SHA-256 canonical JSON.

**Spec:** User-provided “ATOS v2.0 / DeepSeek Harness Orchestrator — Layer 6: Fail-Closed Risk Engine Specification”.

## Global Constraints

- `config/LIVE_LOCK.yaml` remains unchanged: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.
- No live tokens, broker calls, live orders, or changes to release authorization.
- No external agent, plugin, or LLM may authorize capital or mutate the live lock.
- Risk-pass evidence is not final execution authorization.
- The default risk gate is disabled and rejects all requests until explicitly enabled by the owning runtime.

## Review Focus

- Malformed numeric inputs (`None`, booleans, NaN, infinities, overflow) reject deterministically.
- Daily PnL exactly at the configured loss boundary rejects.
- Position and aggregate exposure boundaries cannot be exceeded.
- Exceptions and excessive elapsed evaluation time never return a risk pass.
- A positive risk verdict cannot override the canonical live lock or be interpreted as permission to submit an order.

---

### Task 1: Write the risk-gate matrix tests

**Files:**
- Create: `tests/test_layer6_risk_gate.py`

- [ ] Add happy-path, position breach, daily-loss trip, malformed input, injected exception, timeout, disabled-by-default and exposure checks.
- [ ] Run tests first and confirm they fail because the module does not yet exist.

### Task 2: Implement the pure risk-veto gate

**Files:**
- Create: `runtime/core/layer6_risk_gate.py`

- [ ] Add immutable policy/request/verdict dataclasses and finite numeric validation.
- [ ] Return risk approval only; expose no final authorization flag.
- [ ] Catch all evaluation failures and reject.
- [ ] Reject a result if its synchronous evaluation duration exceeds the configured budget.

### Task 3: Produce a sandbox evidence record

**Files:**
- Create: `scripts/run_layer6_matrix.py`

- [ ] Run the five required cases against the actual gate.
- [ ] Emit UTC timestamped per-case outcomes and latency, canonical SHA-256 payload hash, source/config identity, test environment, and `authorization_granted=false`.
- [ ] Write only to a caller-specified output path; do not check generated evidence into the repository as production certification.

### Task 5: Add strict research metrics and OOS degradation checks

**Files:**
- Create: `assurance/trade_metrics.py`
- Test: `tests/test_trade_metrics.py`

- [ ] Calculate gross profit factor, net expectancy, drawdown in currency and R-multiples.
- [ ] Deduct explicitly supplied spread, commission, payout-cost, and slippage inputs; never infer missing costs.
- [ ] Reject non-finite or invalid inputs and report OOS degradation using the 30% rejection threshold.
- [ ] Keep the report research-only and always set execution authorization to false.

### Task 4: Verify and request independent review

- [ ] Run the targeted matrix in the available Python sandbox.
- [ ] Run code review on the new gate and tests.
- [ ] Confirm LIVE_LOCK remains unchanged and report limitations: no repo-native full-suite run unless CI succeeds; no DeepSeek Harness connection unless verified by a live connector.
