# Stake Policy Provenance Reconciliation

**As of:** 2026-11-03  
**Result:** no conflict resolution approved; ambiguous candidates remain non-authoritative

## Repository evidence

The checked-in implementation in `runtime/core/stake_sizing.py` defines:

- `DEFAULT_MAX_TRADE_RISK_FRACTION = 0.01`
- `DEFAULT_MINIMUM_STAKE = 1.00`
- Stake as `floor_to_cent(verified_available_balance × 0.01)`.
- A hard denial if the computed risk budget is below the broker's USD 1.00 minimum.

The documents `docs/AURELIA_STAKE_POLICY_2026-10-03.md` and `docs/AURELIA_STAKE_POLICY_2026-10-10.md` both identify USD 1.00 as the starting reference/minimum. The latter documents the 1% risk-budget rule and states that USD 100.00 of verified available USD balance is needed before the USD 1.00 minimum can be funded under that rule.

The history for the October 10 policy document and stake sizing module points to commit `fc3759da69997bb31a11e47bc6f75731103ad1a8`. That is source provenance, not a signed approval or proof of an authorized approver.

## Candidate reconciliation

| Candidate | Checked-in source found | Implementation state | Approval/provenance state | Authority |
|---:|---|---|---|---|
| USD 0.35 | No source document or policy commit identified in the inspected repository history | Not implemented as the default/minimum | Missing source, approver, approval date, effective date, capital plane and rationale | **PENDING — NOT AUTHORITATIVE** |
| USD 1.00 | October 3 and October 10 stake policy documents; `runtime/core/stake_sizing.py`; source commit above | **Current implemented minimum** | Source found; formal approval authority/signature and effective approval record not identified | **PENDING PROVENANCE VALIDATION** |
| USD 1.50 | No source document or policy commit identified in the inspected repository history | Not implemented as the default/minimum | Missing source, approver, approval date, effective date, capital plane and rationale | **PENDING — NOT AUTHORITATIVE** |

A value can be implemented without having complete policy-approval provenance. The registry keeps those two states separate. The $1.00 value is the extant code baseline; the registry does not promote it to a newly approved policy based only on a code commit.

## Registry behaviour

`StakePolicyReconciliationRegistry` records the three candidate amounts as pending entries, rejects incomplete records submitted as validated policies, and refuses to return an authoritative policy if more than one validated policy exists for a capital plane.

This branch does not change the numeric sizing rule. It adds policy provenance metadata and a reconciliation interface only.

## Current balance consequence

At an available balance of USD 1.45, a 1% risk budget is USD 0.0145, rounded down to USD 0.01. That is below the USD 1.00 broker minimum, so the current sizing function returns a denial. No minimum override or risk-percentage increase is applied.

## Required evidence before any candidate becomes authoritative

A candidate needs a source document and commit, explicit approval authority, UTC approval and effective dates, capital-plane assignment, rationale, and an explicit validated/rejected status. A commit hash or SHA-256 checksum is not an approval signature.

Until that evidence is recorded and independently reviewed, the $0.35 and $1.50 candidates remain pending and the existing $1.00 code baseline is not promoted by this registry into a separately signed policy.

## Release status

`LIVE_EXECUTION=BLOCKED`; `FINAL_EXECUTION_AUTHORIZATION=false`; `capital_plane_mode=VERIFY_ONLY`.
