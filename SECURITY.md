# Security Policy

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in public issues, pull requests, or discussions.

Use GitHub's private vulnerability reporting feature for this repository if it is enabled. If private reporting is unavailable, contact the repository maintainer privately through GitHub and include the affected commit or version, impact, reproduction steps, and any proposed mitigation. Do not include broker credentials, account tokens, personal account data, or other secrets in the report.

## Scope and response

Reports should identify the affected component, attack prerequisites, impact, reproducible evidence, and any safe mitigation. The maintainers should acknowledge reports, triage severity, and coordinate a fix and disclosure timeline. No response-time SLA is claimed by this policy.

## Trading-system safety

A security report, CI result, dependency update, or agent recommendation does not authorize live trading. Keep `config/LIVE_LOCK.yaml` fail-closed until the independent production release gates have been satisfied. Never include live broker secrets or unredacted account evidence in repository issues, pull requests, logs, or artifacts.
