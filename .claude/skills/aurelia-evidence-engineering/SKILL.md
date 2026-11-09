---
name: aurelia-evidence-engineering
description: Build and validate provenance-bound AURELIA release evidence from genuine workflow, runtime, research, fault-injection, deployment, and security outputs.
---

# AURELIA Evidence Engineering

Read `assurance/certification_evidence.py`, `assurance/evidence_writer.py`, and `assurance/certification_gate.py` before editing evidence.

Trace every artifact producer → raw output → provenance envelope → domain validator. A schema adapter may transform genuine producer output but must not invent observations, counters, or outcome fields to make a validator pass.

Bind exact source commit, configuration hash, data/archive hash, timestamps, issuer, execution environment, and record hash. Evidence files must remain untracked where required by the validator.

## Producer-to-validator mapping

| Evidence | Required source |
|---|---|
| Broker lifecycle | Authenticated read-only account binding, proposal/intent path, deterministic risk/firewall/fence/reconciliation proofs, zero order submission |
| Recovery matrix | Executed fault-injection runs with captured per-scenario outcomes |
| 3,600-second soak | Measured runtime health samples over at least 3,600 real seconds with source/deployment identity and invariant counters |
| Prospective OOS | Sealed immutable collector state/report, archive hash, at least 100 valid OOS samples, and trial accounting |
| Calibration | Actual OOS probabilities/outcomes, at least 100 observations, at least 3 sufficiently populated reliability buckets, finite proper scores, no detected drift |
| Execution economics | Qualified observations plus defensible costs, measured fills/slippage/fees or an explicitly qualified conservative model |
| Security audit | Independent reviewer, defined scope, credential-isolation and capital-bypass findings |
| Deployment | Actual source/build/config/runtime identities and health evidence |
| Strategy eligibility | Passed OOS, calibration, economics, sample/cost stress, and required prospective paper criteria |

## Stop conditions

- An unsealed campaign generates no sealed-OOS evidence.
- Proposal quotes are not realized fill, spread, slippage, or fee data.
- A static fault matrix is not a fault-injection result.
- A health loop without measured invariant counters is not a complete soak.
- Missing, stale, contradictory, unpinned, unrepeatable, or unverified data means BLOCKED.
- A passing unit fixture is not operational evidence.

Never grant live authorization. Certification reports evidence state; human release governance and the deterministic capital plane remain separate.
