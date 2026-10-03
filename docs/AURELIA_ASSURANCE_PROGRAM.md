# AURELIA Assurance Program

## Operating model

AURELIA is divided into five permanent programmes without creating duplicate execution logic:

1. AURELIA CORE — deterministic capital, risk, authorization and broker execution.
2. AURELIA RESEARCH — strategies, models, OOS, statistics and experiments.
3. AURELIA LEARNING — Grok/Dev/specialist counselling, post-trade analysis and validated knowledge.
4. AURELIA ASSURANCE — certification, replay, chaos, red-team, evidence lineage and invariant monitoring.
5. AURELIA OPERATIONS — broker health, infrastructure, monitoring, incident response, backup and recovery.

Architecture:

    RESEARCH ─────┐
    LEARNING ─────┤
    ASSURANCE ────┤
    OPERATIONS ───┤
                  v
          DETERMINISTIC CORE
                  v
          CAPITAL AUTHORIZATION
                  v
                BROKER

All surrounding planes may inform the core. None may override it.

## CAN_TRADE vs SHOULD_TRADE

CAN_TRADE is an infrastructure/capital question.

SHOULD_TRADE is a decision-quality question.

Both must remain independently observable.

## Decision quality dimensions

Maintain independent evidence for:
- market context
- strategy validity
- probability quality
- calibration
- execution quality
- risk quality
- economic quality
- data quality
- knowledge relevance
- regime match

Do not collapse these into one magic score.

## Continuous assurance

After certification, continuously test:
- unauthorized execution
- duplicate economic effect
- stale authorization
- research/capital separation
- probability validity
- temporal integrity
- account isolation
- aggregate exposure
- configuration drift
- deployment drift
- reconciliation integrity
- broker unknown resolution
- kill-switch behavior
- external-content authority boundaries

## Decision replay

Every material decision must be replayable using the exact historical state. Replay is non-executing.

## Shadow twin

Maintain a non-executing decision path and compare:
- shadow decision
- actual decision
- actual broker result

## Near misses

Record prevented failures as first-class operational/research evidence. A near miss is not a successful trade.

## Counterfactuals

For completed or rejected decisions where valid, analyse no-trade and alternative-valid-action counterfactuals. Counterfactuals are research-only.

## Strategy demotion

Strategies can move:
RESEARCH -> VALIDATION -> OOS -> CANDIDATE -> CANARY -> PRODUCTION -> MONITORED -> DEGRADED -> SUSPENDED -> REVALIDATION -> REINSTATED

Demotion does not authorize automatic strategy rewrites.

## Research discipline

Track experiment count and search degrees of freedom. Repeated experimentation against the same OOS set must not manufacture confidence.

## Change discipline

No new subsystem should be added unless its information, safety or evidentiary value exceeds its introduced failure surface and operational cost.

## Production posture

Certification is not permanent. Material changes invalidate applicable evidence and trigger revalidation.
