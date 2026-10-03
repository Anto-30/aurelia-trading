# AURELIA Counterfactual and Near-Miss Framework

## Counterfactual analysis

For each eligible decision, capture:
- actual decision
- no-trade outcome
- alternative valid entry where identifiable
- alternative valid exit where identifiable
- alternative valid duration where contract semantics permit
- alternative valid stake where risk policy permits

Counterfactuals are research evidence only. They cannot retroactively alter authorization.

Use attribution to distinguish:
- bad signal
- good signal / bad entry
- good entry / bad execution
- good execution / valid loss
- random outcome

## Opportunity-cost analysis

Study blocked or rejected signals to understand whether controls are overly restrictive. Never loosen controls automatically from this analysis.

## Near misses

First-class record types should include:
- duplicate prevented
- stale authorization prevented
- exposure threshold nearly reached
- reconciliation near-failure
- stale-data near-miss
- firewall blocked unsafe order
- kill-switch activation
- credential access attempt
- deployment/config drift

Each near miss should preserve:
- timestamp
- correlation ID
- state before
- trigger
- control that intervened
- expected outcome
- observed outcome
- recovery
- invariant status
- counselling record

## Learning rule

A near miss informs learning; it does not become an automatic rule change.

Near misses should be reviewed in aggregate.
