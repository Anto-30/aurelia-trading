# AURELIA — Source-Recovery Recheck / Corrective Closure Evidence

Date: 2026-10-03 EAT
Repository: Anto-30/aurelia-trading
Branch: aurelia-final-assurance-2026-10-03

## Purpose

This recheck verifies whether the previously missing authoritative AURELIA runtime has become accessible and records corrective assurance changes made after the original closure.

## Fresh recovery findings

- GitHub Anto-30/aurelia-trading remains a small repository whose default main branch does not expose the production runtime. The assurance branch contains governance, assurance, and evidence artifacts only.
- GitHub commit searches scoped to this repository returned no matches for v1.27 or deriv_adapter.
- The separate Anto-30/Aurelia-trading- repository remains readme-only with no AURELIA runtime branches.
- Notion direct content search continues to locate the historical Aurelia trading systems page and the two recorded v1.27 package names. The page is historical/unverified; the package bytes are not exposed by the direct page result.
- The plan-gated historical Notion agent/session indexing capability was not usable. Direct Notion page/content search was usable and was sufficient to establish the historical reference, but it does not expose the package bytes.
- Dropbox shared-link inventory is empty.
- Railway project AURELIA-Production-Worker exists with a production environment and zero services. No service was created or activated.
- Supabase project Anto-30's Project is INACTIVE. A table-inspection request timed out; no database schema/state conclusion is drawn.
- The connected Vercel workspace exposes only the Tales & Trails projects; no AURELIA deployment was identified.
- Remote Desktop Commander has no connected development device.

## Authoritative-source decision

AUTHORITATIVE_RUNTIME_SOURCE = NOT_RECOVERED

The historical Notion record is evidence that a v1.27 package was documented on 2026-09-20, not evidence that the package is currently recoverable. No archive, source tree, deployment artifact, or runtime image accessible through the connected routes was accepted as the authoritative implementation.

## Corrective assurance change

The assurance helper previously named blind_resubmit_allowed() returned True whenever the broker state was known. That was broader than its safety name and allowed a caller to interpret “known” as sufficient for resubmission.

It now always returns False. A new economic action must instead pass through explicit recovery/reconciliation and a newly authorized intent.

The contract suite was expanded to:
- exercise every mandatory boolean authorization control independently;
- verify stale authorization and unknown broker state each deny;
- test the full inclusive 0.55–0.75 probability boundary without clipping;
- verify the $1.50 boundary for order affordability;
- verify blind resubmission is never permitted.

## Result

The correction strengthens the assurance plane only. It does not implement, replace, or activate the AURELIA runtime.

ASSIGNMENT = CLOSED
ASSURANCE_WORK_EXECUTED = COMPLETE
RECOVERY_SWEEP = COMPLETE
IMPLEMENTATION_CERTIFICATION = BLOCKED
FINAL_EXECUTION_AUTHORIZATION = FALSE
LIVE_EXECUTION_ALLOWED = FALSE
LIVE_ORDERS = 0

## Certification boundary

Authoritative source recovery remains the primary implementation-level blocker. Once the runtime is recovered, certification must still independently establish broker lifecycle integrity, crash/restart/idempotency/concurrency behavior, 3600-second adversarial soak, prospective OOS, calibration, execution economics, deployment integrity, credential isolation, auditability, and controlled canary evidence.

No missing-runtime claim has been repaired by reconstruction or substitution.
