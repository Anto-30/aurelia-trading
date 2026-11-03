# PR #191 Independent Review Package

## Scope

PR #191 adds a disabled-by-default Layer 6 risk veto and research metrics. The
follow-on work adds source-bound boundary contracts, kill-switch/lock/
reconciliation regression tests, and a strictly read-only Deriv state verifier.

The change does not grant capital authority, make Layer 6 the execution
gateway, or modify release policy.

## Architecture review checklist

- [ ] Layer 6 can only return RiskVerdict; it has no capital-authority getter,
      broker client, proposal or submission method.
- [ ] Policy and all numeric/exposure request values are bound to a declared
      schema, source ID, account currency/unit, UTC capture time and SHA-256
      checksum.
- [ ] The reviewer understands that SHA-256 is not a digital signature or
      source authentication.
- [ ] The existing CapitalPlaneExecutor is still the only capital-moving
      authority.
- [ ] A positive risk verdict cannot bypass LIVE_LOCK, the kill switch or
      reconciliation failure.
- [ ] The alternate runtime/broker/factory.py construction path is reviewed
      separately for the required persistent daily-risk guard before any
      production use.
- [ ] No Shadow component receives Deriv credentials or an order-submission
      method.
- [ ] No changes are made to config/LIVE_LOCK.yaml.

## Test and workflow evidence required

Run the focused boundary and read-only tests:

    python -m unittest tests.test_layer6_gateway_boundary tests.test_deriv_read_only_state -v

Then run the full repository Assurance workflow on the exact proposed head.
The reviewer must inspect the actual workflow result and logs; a local subset
or an earlier commit is not sufficient.

The read-only Deriv verifier is not a mandatory CI call against a real account.
Its unit tests must verify that the API sequence contains only balance,
portfolio and statement reads and that unavailable broker state fails closed.
A real authenticated run requires the owner's configured secret material and
must remain read-only.

## Current integration limitations

The new Layer 6 source-bound adapter is not yet connected to the production
signal/readiness path. The live loop currently consumes risk-warden approval
from the existing readiness attestation bundle and does not yet issue the
complete source-bound Layer 6 input. Do not describe this PR as completing
production Layer 6 integration.

The configured Deriv authenticated-session evidence was not present in the
latest Assurance run, so no authenticated broker state or account balance was
proven by that run. The persistent worker, runtime identity, signing key,
strategy eligibility, prospective out-of-sample, calibration, economics and
3600-second soak evidence also remain outstanding.

## Reviewer decision

The reviewer must be independent of the implementation author and must
inspect the exact head commit. Approve only if the changed code, exact-head
tests, full Assurance run, policy provenance and authority ordering are
verified. Otherwise request changes and list exact file/line references.

No reviewer identity is assumed by this document. No Claude, DeepSeek, Hermes,
CodeRabbit or other external-agent review is claimed unless a connected tool
actually returns review evidence.
