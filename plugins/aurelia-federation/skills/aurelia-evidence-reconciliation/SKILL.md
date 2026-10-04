---
name: aurelia-evidence-reconciliation
description: Use when AURELIA status documents, reports, issues, dashboards, or evidence records may be stale or contradictory.
version: 1.0.0
---

Reconcile current main tip, CI run identity, immutable evidence artifacts, release lock, and operational documents.

Required runtime evidence fields:
- source commit
- runtime image identity when applicable
- workflow/run identifier
- evidence class
- target and observed duration
- failure counts
- capital-protection state
- authentication and transaction state

Correct stale metadata without changing the evidence class or fabricating missing evidence.
