# Independent Security Review Request — PR #256

**Repository:** `Anto-30/aurelia-trading`  
**Pull request:** https://github.com/Anto-30/aurelia-trading/pull/256  
**Title:** `security: split Deriv public research and account evidence planes`  
**Head branch:** `security/split-deriv-research-account-planes-20261102`  
**Exact head commit:** `c83d16ec25be3f7a8bea813687ab76bbe9695d9b`  
**Base:** `main`  
**PR state:** Open, non-draft, not merged  
**Reviewer:** Awaiting repository owner to select an independent security reviewer

## CI evidence at the exact head

- AURELIA Assurance: https://github.com/Anto-30/aurelia-trading/actions/runs/42020783942 — success
- AURELIA Agent Federation Audit: https://github.com/Anto-30/aurelia-trading/actions/runs/42020784070 — success
- AURELIA Agent Continuity Watchdog: https://github.com/Anto-30/aurelia-trading/actions/runs/42020783848 — success

These checks establish the recorded CI result for this commit. They do not substitute for independent security review, credential revocation, host verification, or release authorization.

## Review mandate

Review the exact head commit above, not a moving branch tip. Verify the following:

1. **Credential-plane isolation**
   - General Assurance and public research workflows do not attach the production environment or inject Deriv account credentials.
   - Research code rejects account credential variables at client creation and again at request time.
   - The public Deriv client does not add bearer tokens, PATs, OAuth tokens, OTPs, or cookies to its transport.
   - Account authentication fails closed when the broker permission required by AURELIA is not demonstrably read-only.

2. **Request-surface restrictions**
   - Public research actions are allowlisted.
   - Capital-moving actions such as `buy` are rejected.
   - Proposal retrieval is not confused with purchase/order submission.

3. **Secret handling**
   - No credential values are committed, printed, or placed in CI artifacts.
   - Secret provisioning does not create an unsupported read-only token or silently fall back to a trade-capable PAT.
   - Assess Git history, workflow expressions, artifact paths, and log exposure.

4. **Deployment and release controls**
   - Privileged deployment workflows are branch/environment gated.
   - LIVE deployment remains blocked when the required account permission scope is unavailable.
   - `config/LIVE_LOCK.yaml` remains unchanged and fail-closed.

5. **Regression coverage**
   - Authentication-gate tests cover PAT, generic-token, refresh-token, OAuth, and late-injected credential cases.
   - Workflow tests prove production secrets are not exposed to general Assurance or public research.
   - Any uncovered edge case is documented with a reproducer and a test.

## Reviewer disposition

Record one of: `APPROVE`, `REQUEST_CHANGES`, or `INSUFFICIENT_EVIDENCE`.

Do not approve solely because CI is green. Any unresolved credential leak, unverified permission assumption, or path to broker order submission from the research/shadow plane is a blocking finding.

## Required evidence after review

- A GitHub review submitted by an independent reviewer against the exact reviewed head SHA.
- Inline comments or a written review summary with findings and severity.
- A fresh exact-head CI run after any requested changes.
- Separate owner confirmation that the exposed PAT was revoked and its exposure audited.

**Status:** `INDEPENDENT_REVIEW_PENDING`  
**Credential revocation:** `OWNER_ACTION_REQUIRED`  
**Live execution:** `BLOCKED`  
**Final execution authorization:** `false`
