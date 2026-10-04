---
name: aurelia-evidence-reconciliation
description: Use when AURELIA reports, dashboards, README files, issues, or operational artifacts may disagree with verified CI evidence or current repository state.
version: 1.0.0
---

# Evidence Reconciliation

Treat evidence as a typed record, not prose.

Required fields for runtime evidence:
- source commit
- runtime image identity where applicable
- workflow/run identifier
- evidence class
- target and observed duration where applicable
- failure counts
- capital-protection state
- authentication/transaction status

Reconcile:
1. current `main` tip;
2. latest verified CI result;
3. immutable evidence artifact;
4. committed status documents;
5. open certification issues.

Flag any contradiction such as:
- a passed 3600-second non-production soak described as NOT_RUN;
- stale commit IDs presented as current;
- simulation described as production;
- authenticated-session code described as authenticated-session evidence;
- operator-reported broker state described as independently verified.

Do not resolve contradictions by downgrading actual evidence. Correct the stale metadata and preserve historical artifacts as historical records.
