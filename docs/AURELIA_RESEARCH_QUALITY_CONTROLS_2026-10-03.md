# AURELIA Research Quality Controls

Research quality remains separate from capital authorization.

Calibration evidence must include Brier score, log loss, reliability buckets, sample counts and drift monitoring. A valid probability value is not evidence of calibration.

Execution economics must separate gross P&L from fees, slippage and other measurable execution costs. Missing cost inputs preserve NET_EXPECTANCY=UNDETERMINED rather than manufacturing a value.

Research records must retain trial count, search degrees of freedom and OOS reuse. Reusing a prospective OOS set is explicitly surfaced.

Post-trade attribution must retain expected versus actual entry/exit, gross P&L, fees, slippage and latency so strategy, model, data and execution failures can be distinguished.

No single completed trade is permitted to promote, rewrite or silently modify a strategy. Learning outputs must enter the existing validation/approval path.

Drift is a monitoring signal, not an automatic strategy rewrite. Material drift should suspend or trigger review according to the existing deterministic policy.

## Soak evidence

A genuine 3,600-second non-live adversarial execution is required for certification. The validation contract rejects shorter runs as insufficient evidence.

The absence of the authoritative AURELIA runtime means the full soak is currently NOT_RUN / UNPROVEN.
