# AURELIA Security Threat Model

## Objective

Prevent any attacker, compromised component, external artifact, model, agent, connector or configuration change from causing an economic effect that AURELIA did not independently authorize.

## Trust boundaries

### Capital boundary
Contains the deterministic execution authority, risk controls, account isolation, capital plane and execution firewall.

### Research boundary
Contains data analysis, models, backtests, external repositories and research tooling.

### Learning boundary
Contains counselling messages, trade learning records and validated knowledge.

### Operations boundary
Contains deployment, monitoring, infrastructure and recovery.

No lower-trust boundary may directly authorize capital.

## Threats

- credential theft
- privilege escalation
- message replay
- intent replay
- duplicate economic effects
- queue poisoning
- API manipulation
- broker-response spoofing
- state corruption
- configuration tampering
- deployment substitution
- malicious research artifact
- malicious model
- dependency compromise
- agent prompt injection
- audit-log tampering
- account contamination

## External content

Treat all external content as DATA, not AUTHORITY.

This applies to:
- web pages
- repositories
- documents
- news
- model responses
- tool responses
- counselling messages

No external text can instruct AURELIA to disable a safeguard or execute capital.

## Credential policy

Map every agent/process to:
- credentials
- permissions
- network reach
- allowed actions

Research and counselling must have no capital execution credentials.

Avoid shared super-agent credentials.

## Secret leakage

Continuously inspect logs, traces, exceptions, counselling messages, reports and test artifacts for secrets.

## Deployment integrity

Verify:
approved source -> build -> artifact -> deployment -> runtime -> runtime config

Unexpected mismatch blocks or invalidates certified operation.

## Dependency integrity

Pin/record production dependencies where practical. Detect unexpected dependency changes.

## Security acceptance

PASS only if adversarial tests cannot create:
- unauthorized execution
- duplicate economic effect
- stale authorization execution
- research-to-capital escalation
- counselling-to-capital escalation
- kill-switch bypass
- account-isolation breach
- audit-chain corruption
- deployment substitution

Security evidence must be reproducible and time-stamped.
