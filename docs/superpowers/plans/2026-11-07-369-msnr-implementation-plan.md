# AURELIA 369/MSNR Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a separately versioned, research-only 369/MSNR candidate and deterministic cost-aware event simulator without changing capital or execution authority.

**Architecture:** Add a new research module that composes the existing closed-bar MSNR detector with 369 levels, close-time eligibility, displacement and 3R gates. Add a separate event-driven simulator and explicit strategy-registry entry; reuse existing cost-profile and walk-forward governance rather than duplicating them.

**Tech Stack:** Python 3, standard-library `zoneinfo`, existing dataclasses and unittest/pytest conventions, existing AURELIA research and validation modules.

**Spec:** `docs/superpowers/specs/2026-11-07-369-msnr-research-design.md`

## Global Constraints

- Research-only; no capital authority and no order submission.
- `config/LIVE_LOCK.yaml` remains unchanged and `LIVE_EXECUTION: BLOCKED`.
- Signal eligibility is based on confirmed candle close in `[09:45, 10:00)` `America/New_York`.
- Entry uses the next available bar open; never the signal close.
- Gross target-distance threshold is at least 3.0R from the actual simulated entry.
- Unknown instrument scale, tick precision, data provenance, or cost profile blocks qualification.
- Preserve existing MSNR behavior; implement a distinct versioned strategy.
- No look-ahead; all indicators and swing confirmations use completed bars only.
- No new third-party dependency without a demonstrated need.
- No code or test changes before the relevant failing test is written and observed failing.

## Review Focus

1. **DST and timezone boundary:** local close conversion must preserve correct New York wall-clock eligibility across spring-forward and fall-back transitions.
2. **M15 bar semantics:** open-labelled OHLC timestamps must be converted to close timestamps using the declared timeframe; do not treat an open label as a close.
3. **Anchor precision and unsupported symbols:** fractional anchor preservation and tick-size quantization must not silently round to an invalid tradable level.
4. **Gap and intrabar ambiguity:** next-open gaps and bars touching both stop and target must not create optimistic fills.
5. **Unknown cost/data provenance:** missing or stale cost fields, incomplete bars, and unverified instrument mappings must prevent qualification rather than default to zero.

---

### Task 1: 369 arithmetic and timing primitives

**Files:**
- Create: `research/labs/three_sixty_nine_msnr.py`
- Test: `research/labs/tests/test_three_sixty_nine_msnr.py`

**Interfaces:**
- Consumes: `StrategyBar`, `StrategyCandidate`, `MSNRConfig`, and `detect_msnr_liquidity_sweep` from `research/labs/deterministic_intraday_strategies.py`.
- Produces:
  - `digital_root(integer_price: int) -> int`
  - `level_step_for_root(root: int) -> int`
  - `build_369_levels(anchor_price: float, *, direction: str, level_count: int = 4) -> tuple[float, ...]`
  - `signal_close_is_eligible(close_timestamp: datetime) -> bool`
  - `bar_close_timestamp(bar_open_timestamp: datetime, timeframe_seconds: int) -> datetime`

- [ ] **Step 1: Write failing unit tests** for roots 1–9, mappings 1/4/7→12, 2/5/8→15, 3/6/9→18, integer-only root input, fractional-anchor preservation, direction/order/count, invalid root/price, timezone-aware timestamps, 09:45 inclusion, 10:00 exclusion, and DST transitions.
- [ ] **Step 2: Run the focused test module** and confirm failures are caused by missing functions or unimplemented behavior.
- [ ] **Step 3: Implement the five public functions** in `research/labs/three_sixty_nine_msnr.py`; reject naive timestamps and invalid timeframe durations.
- [ ] **Step 4: Run the focused tests** and confirm all pass.
- [ ] **Step 5: Commit** the module and tests with message `feat(research): add 369 arithmetic and close-time gates`.

### Task 2: Candidate construction and 3R/displacement filters

**Files:**
- Modify: `research/labs/three_sixty_nine_msnr.py`
- Test: `research/labs/tests/test_three_sixty_nine_msnr.py`

**Interfaces:**
- Consumes: Task 1 primitives and the existing MSNR detector.
- Produces:
  - `ThreeSixtyNineMSNRConfig` with explicit instrument id, tick size, price scale, MSNR config, displacement toggle, EMA/ATR filter toggle, and minimum gross R defaulting to 3.0.
  - `ThreeSixtyNineMSNRCandidate` with signal close timestamp, next-bar entry timestamp/price when supplied, stop, selected 369 target, gross R, variant id, and research-only authority flags.
  - `evaluate_369_msnr_candidate(bars: Sequence[StrategyBar], *, config: ThreeSixtyNineMSNRConfig) -> ThreeSixtyNineMSNRCandidate | None`

- [ ] **Step 1: Write failing tests** for MSNR candidate composition, close-window gating, next-bar-open price, long/short 369 target selection, displacement body > 1.5 × prior-three-body mean, no future-bar use, 3R inclusion/rejection, and authority flags fixed false.
- [ ] **Step 2: Run the focused tests** and confirm expected failures.
- [ ] **Step 3: Implement candidate construction** while reusing the existing MSNR detector; preserve separate baseline, displacement, and EMA/ATR variant identifiers.
- [ ] **Step 4: Run focused tests** and verify candidate behavior.
- [ ] **Step 5: Commit** with message `feat(research): compose 369 MSNR candidates`.

### Task 3: Event-driven research simulator

**Files:**
- Create: `research/labs/three_sixty_nine_simulator.py`
- Test: `research/labs/tests/test_three_sixty_nine_simulator.py`

**Interfaces:**
- Consumes: Task 2 candidate, existing `InstrumentCostProfile` from `research/labs/intraday_bias_cost_model.py`.
- Produces:
  - `SimulatedTrade` immutable result containing entry/exit timestamps and prices, stop/target, gross R, itemized costs, net P&L/R, exit reason, and provenance identifiers.
  - `simulate_candidate(candidate, bars, *, cost_profile, tick_size, ...) -> SimulatedTrade | None`
  - `simulate_candidates(candidates, bars_by_symbol, *, cost_profiles, ...) -> tuple[SimulatedTrade, ...]`

- [ ] **Step 1: Write failing tests** for next-open fills, gaps through stop/target, stop-first ambiguous bars, separate spread/slippage/commission/fees, unknown/stale cost rejection, no-fill/missing-bar behavior, and explicit end-of-data exit semantics.
- [ ] **Step 2: Run focused simulator tests** and confirm failures.
- [ ] **Step 3: Implement deterministic event processing** with conservative OHLC sequencing and verified cost-profile validation; do not call broker or execution APIs.
- [ ] **Step 4: Run focused simulator tests** and verify all outcomes and cost calculations.
- [ ] **Step 5: Commit** with message `feat(research): add conservative 369 event simulator`.

### Task 4: Strategy registry and evidence contract

**Files:**
- Modify: `config/strategy_registry.json`
- Create: `research/labs/tests/test_three_sixty_nine_registry.py`

**Interfaces:**
- Consumes: Task 2 strategy id/version and Task 3 evidence fields.
- Produces: a separate `THREE_SIXTY_NINE_MSNR` research registry entry with `implementation_status: RESEARCH_ONLY`, `qualification_status: RESEARCH_ONLY_UNQUALIFIED`, unknown instrument/cost status, and all OOS/robustness/forward-test/soak gates NOT_RUN.

- [ ] **Step 1: Write failing registry tests** proving the new strategy is independently registered, existing MSNR entry is unchanged, and all qualification gates fail closed.
- [ ] **Step 2: Run the registry test** and confirm the missing-entry failure.
- [ ] **Step 3: Add the new registry entry only**; do not promote or edit existing strategies.
- [ ] **Step 4: Run registry and JSON parsing tests** and verify unchanged existing entries.
- [ ] **Step 5: Commit** with message `chore(research): register unqualified 369 MSNR variant`.

### Task 5: Full verification and research-readiness report

**Files:**
- Create: `docs/research/369-msnr-verification-report-template.md`
- No capital-plane, broker, or LIVE_LOCK files may be modified.

**Interfaces:**
- Consumes: Tasks 1–4, current research governance, data provenance, and verified cost profiles.
- Produces: a reproducible report template and a gate matrix separating unit correctness, data readiness, cost readiness, historical performance, OOS evidence, and qualification status.

- [ ] **Step 1: Add report-template tests** for required evidence fields, dataset/config/code hashes, per-symbol/timeframe/regime segmentation, net metrics, limitations, and explicit unqualified status.
- [ ] **Step 2: Run template tests** and confirm missing requirements fail.
- [ ] **Step 3: Add the report template** with no fabricated results or placeholder performance claims.
- [ ] **Step 4: Run the full repository assurance and runtime test commands** from README:
  - `python -m unittest discover -s assurance -p 'test_*.py' -v`
  - `python -m unittest discover -s tests -p 'test_*.py' -v`
  - plus the focused `research/labs/tests` suite using the repository's supported test runner.
- [ ] **Step 5: Inspect the final diff**, verify `config/LIVE_LOCK.yaml` is byte-for-byte unchanged, verify no capital/execution paths changed, and record CI status for the exact branch head.
- [ ] **Step 6: Commit** with message `docs(research): add 369 MSNR verification report template`.

## Execution notes

- The repository's connected GitHub integration has read/write access, but this session has not demonstrated a local shell or Python runtime attached to the repository. Do not claim local tests ran unless an actual runtime is connected. Use the repository's CI for executable verification and record exact run IDs/commit SHAs.
- Do not fabricate historical market data or cost profiles. A backtest is blocked until source-backed, instrument-specific bars and verified costs are available.
- The 08:49:55 marker is excluded until its exact source definition is provided.
- The design's protected-swing anchor convention and instrument scaling/tick precision require source confirmation before qualification.
- A minimum of 100 trades applies per strategy × symbol × regime cell where the current qualification policy requires it; an aggregate 100 trades is not a substitute.
- Keep all changes research-only. Do not modify `config/LIVE_LOCK.yaml`, capital plane, execution firewall, broker adapters, risk authority, or deployment/release policy.
