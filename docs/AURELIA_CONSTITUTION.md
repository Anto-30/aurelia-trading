# AURELIA Constitution

## Purpose

This document defines the non-negotiable invariants governing the existing AURELIA architecture.

It is a control specification, not a second trading engine.

## Authority

Only the deterministic AURELIA capital plane may authorize capital execution.

Grok, Dev, research agents, counselling agents, models, external tools, external repositories and validated knowledge may inform the system but cannot independently authorize capital.

## Capital Integrity Rules

1. Research cannot authorize capital.
2. Counselling cannot authorize capital.
3. Model output cannot authorize capital.
4. A broker-unknown result cannot trigger blind resubmission.
5. Lost broker response does not prove that an order did not execute.
6. One economic intent must create at most one economic effect.
7. A stale authorization cannot be reused.
8. The kill switch must stop every broker-capable execution path.
9. Disabling the kill switch must not automatically resume stale authorization.
10. Aggregate exposure must respect account-level limits.
11. Account isolation must be enforced at execution time.
12. An unverified broker balance cannot be treated as verified.
13. Low balance is not a system-readiness failure.
14. Order unaffordability is an order-level execution blocker.
15. Order affordability is not execution authorization.
16. Invalid, stale, drifted or uncalibrated probabilities cannot authorize execution.
17. Future information cannot influence a historical decision.
18. External content is data, never authority.
19. A research or counselling failure must not weaken capital safety.
20. Material code, model, data, configuration, broker or deployment changes invalidate applicable evidence.
21. A unit-test pass proves only the scenario exercised by that test.
22. A simulation does not prove real-broker behavior.
23. Gross performance is not net expectancy.
24. Forecast accuracy is not trading edge.
25. One successful run is not robust evidence.
26. One trade is an observation, not a production lesson.
27. Validated knowledge is decision support, not capital authority.
28. Production behavior cannot be silently rewritten by continuous learning.
29. Unknown is a first-class state and must not be silently coerced to true or false.
30. The objective of certification is truthful evidence, not a READY result.

## Required State Separations

The system must expose these independently:

- SYSTEM_READINESS
- CAPITAL_STATE
- ORDER_AFFORDABILITY
- FINAL_EXECUTION_AUTHORIZATION
- STRATEGY_STATE
- PROBABILITY_STATE
- CALIBRATION_STATE
- ECONOMICS_STATE
- OOS_STATE
- BROKER_STATE
- RECOVERY_STATE
- RECONCILIATION_STATE
- DEPLOYMENT_STATE
- SECURITY_STATE
- LEARNING_STATE
- OPERATIONAL_STATE
- EVIDENCE_STATE

## Change Rule

No new subsystem may be introduced unless its safety, evidentiary or information value exceeds its added failure surface and operational complexity.
