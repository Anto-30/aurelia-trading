# AURELIA Assurance Plane

These modules are execution-neutral assurance primitives.

They do not:
- submit broker orders
- hold capital credentials
- authorize live capital
- bypass existing AURELIA capital controls
- replace the production execution engine

The assurance plane provides:
- invariant predicates
- execution-state transition checks
- typed evidence/near-miss/experiment records
- repository certification gating
- CI regression checks

A certification failure is intentional when the underlying implementation or required evidence is absent.

A passing assurance-contract test proves only the contract exercised by that test. It does not prove production readiness.

The assurance gate never flips live authorization.
