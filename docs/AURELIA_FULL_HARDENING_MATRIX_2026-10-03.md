# AURELIA Full Hardening Matrix

This branch maps the assurance recommendations to machine-checkable contracts in the existing architecture.

- Certification constitution and explicit fail-closed states.
- Evidence expiration and deterministic evidence envelopes.
- Explicit UNKNOWN handling.
- Concurrency, idempotency and broker-outcome recovery.
- UTC clock integrity and decision-time checks.
- Market-data integrity and multi-timeframe synchronization.
- Leakage prevention and exact historical decision replay.
- Separation of forecast confidence, trade probability and final authorization.
- Aggregate exposure accounting.
- Kill-switch persistence and fresh authorization after reset.
- Configuration digest integrity.
- Research and counselling privilege isolation.
- Near-miss and incident evidence.
- Shadow decision comparison.
- Post-trade attribution and net P&L.
- Probability calibration and drift monitoring.
- Multiple-testing accounting.
- Backup/restore reconciliation.
- Deployment lineage and runtime/config matching.
- Continuous invariant monitoring and no silent degradation.
- Adversarial soak protocol.
- Explicit full-balance stake ceiling at the affordability layer.

The affordability rule is: a fresh, authoritative verified available balance is the maximum amount the order layer may request. A request equal to 100% of that balance is permitted by the affordability layer, but is never sufficient by itself for authorization. The existing risk, broker, contract, account-isolation, reconciliation, firewall, kill-switch and capital-authorization controls remain mandatory.

The hardening layer never grants live authorization and never reconstructs a missing runtime.
