# AURELIA Intraday Bias Research Operating Spec

Status: research-only. No capital authority. No live execution authority.

## Purpose

Measure recurring directional drift by time bucket without assuming that a historical tendency is an executable edge.

## Experiment

For hourly UTC bars, signal hour H enters at open(H+1) and exits at open(H+2). No stops, targets, discretionary filters, or execution authorization are part of the base experiment.

## Evidence ladder

1. Accumulate immutable prospective observations.
2. Validate data continuity and provenance.
3. Freeze explicit IS/OOS periods before evaluation.
4. Calculate raw and cost-adjusted statistics.
5. Apply multiple-testing correction across the tested family.
6. Require minimum sample sizes and OOS survival.
7. Classify conservatively.
8. Revalidate when data, regime, or research generation becomes stale.

## Minimum Level-1 target

The default validator requires 240 total observations, 120 IS observations, and 60 OOS observations. These are research defaults, not claims of universal statistical sufficiency.

## Multiple testing

Benjamini-Hochberg adjusted q-values are used as a screening control. They do not establish independence, causality, or tradability. Serial correlation and market-regime dependence require separate treatment.

## Cost boundary

Raw drift is never sufficient for a tradability claim. Cost-adjusted expectancy must remain positive under an explicitly documented cost/slippage model before a candidate can progress.

## Execution boundary

The passport has no execution command. bias_to_execution_command intentionally raises. Any future contextual integration must pass through AURELIA's existing probability, risk, policy, firewall, capital-plane, account-isolation, and reconciliation controls.

## Data collection

The current repository does not contain multi-year intraday history for this experiment. The correct action is to accumulate prospective observations rather than fabricate historical evidence.
