# Layer 6 and Capital Plane Boundary

## Purpose

Layer 6 evaluates a proposed exposure and returns a deterministic risk verdict.
It does not own account capital, approve the final transaction, clear a kill
switch, create an order proposal, submit an order, or change release policy.

The only capital-moving orchestration authority in this repository remains
runtime.broker.executor.CapitalPlaneExecutor. The canonical gateway
independently checks the immutable release configuration, its durable kill
switch, account binding, current broker balance, daily risk guard, broker
portfolio, reconciliation, fencing, proposal binding and idempotency before
calling the Deriv adapter's submission method.

## Implemented contract

runtime.core.boundary_contracts defines:

- IRiskEngine: accepts a RiskEvaluationInput and returns RiskVerdict only.
- RiskProvenance: binds a source identifier, UTC capture time, schema version,
  SHA-256 checksum, account currency and unit.
- Layer6RiskEngine: validates policy and input provenance before delegating to
  the existing Layer6RiskGate.
- IExecutionGateway: describes the real CapitalPlaneExecutor control surface,
  not a second broker client.

The contract intentionally does not expose a capital-authority getter. A risk
engine cannot query, allocate, unlock, or mutate capital authority. A passing
risk verdict is only one boolean input into the existing gateway's conjunctive
authorization checks.

## Provenance semantics

The input checksum covers the complete serialized RiskRequest, including
stake, available balance, daily PnL, worst-case loss and all exposure buckets.
The policy checksum covers the complete RiskPolicy. A source ID, schema
version, currency/unit and freshness window must also match the constructor's
explicit expectations.

SHA-256 is tamper-evident payload binding only. It is not a signature, does not
prove that the claimed source is genuine, and does not replace authenticated
broker identity or independently issued attestations. Policy provenance must
be issued by a trusted configuration/evidence authority before this adapter
can be enabled.

## Production integration status

The boundary module is an isolated, tested contract. It is **not yet wired
into the canonical production signal loop**. The present runtime derives
risk_approved from its current source-bound readiness/risk-warden attestation
bundle; it does not yet construct the complete source-bound
RiskEvaluationInput with a trusted policy provenance issuer.

Do not replace that production input with a strategy- or agent-supplied
boolean, synthetic checksum, fabricated market state or hard-coded risk
threshold. Do not enable this adapter in production until all of the
following exist and are reviewed:

1. A trusted policy source with explicit account currency and unit semantics.
2. A source-bound risk snapshot that includes every numeric/exposure field,
   account identity, capture time, schema version and checksum.
3. A canonical runtime integration that invokes Layer 6 and passes only its
   risk verdict into CapitalPlaneExecutor.
4. An integration test against the actual capital-plane construction path
   proving LIVE_LOCK, kill switch, reconciliation, stale broker state,
   idempotency and fencing still deny even when Layer 6 approves.
5. A current independent review and passing protected Assurance workflow.

## Shadow and research planes

Do not introduce a router that can send arbitrary intent to a live gateway.
Research/paper execution must record local simulated outcomes through a
separate component that has no Deriv adapter, account token, proposal method
or broker submission interface. This patch does not add a Shadow router because
the repository's existing non-LIVE execution path is deliberately rejected by
CapitalPlaneExecutor.execute; making a shadow mode operational is a separate
design with its own persistence and isolation tests.

## Non-negotiable release controls

- config/LIVE_LOCK.yaml remains unchanged.
- LIVE_EXECUTION=BLOCKED.
- FINAL_EXECUTION_AUTHORIZATION=false.
- capital_plane_mode=VERIFY_ONLY.
- No live credentials are placed in Layer 6, research workers or Shadow components.
- No external LLM, agent, plugin or repository receives capital authority.
- Unknown or invalid state blocks rather than falling back to permissive defaults.
