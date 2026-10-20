# Odysseus Self-Hosted AI Workspace — Source Triage

Date: 2026-10-17  
Repository: https://github.com/odysseus-dev/odysseus  
Reviewed source pin: `9712a5400175f8beacb215cefed1dad6935627df` (GitHub commits API `HEAD`; verify the intended branch before any build)  
Repository-reported license: AGPL-3.0-or-later  
Disposition: `SANDBOX_ONLY`; no production deployment or AURELIA runtime integration approved.

## What it is

The README describes a self-hosted AI workspace for chat, agents, research, documents, email, notes, calendar and local model workflows. It advertises tool/MCP support, files, shell, skills and memory. It is a general agent workspace, not a trading engine or deterministic risk authority.

## Security gates

The README explicitly warns that local tools are powerful and says to keep `AUTH_ENABLED=true` for any network-accessible deployment and `LOCALHOST_BYPASS=false` outside local development. It also advises against exposing raw model/service ports publicly. These are important operator instructions, not independent proof of secure defaults.

Before any isolated trial:
1. Confirm branch and commit pin (the README states `dev` is the default branch and receives newest changes first; `main` is described as more curated).
2. Review Docker Compose ports, bind addresses, network exposure, container capabilities, volumes, user IDs, and privilege escalation.
3. Verify authentication, first-admin password lifecycle, 2FA, localhost bypass, session/cookie policy, CSRF, and secret storage.
4. Audit shell/file/MCP/skills permissions; deny access to host credentials, AURELIA repositories with write permission, broker endpoints, and production secrets.
5. Restrict egress and extension/tool installation; defend against prompt injection and untrusted document instructions.
6. Run pinned dependency/SBOM, secret, static and container scans; test auth and access-control boundaries before a network-exposed deployment.
7. Review AGPL-3.0-or-later obligations and third-party dependencies before redistribution or modification.

## AURELIA fit

Potentially useful only as an isolated operator research workspace. It must not host or control AURELIA's capital plane, risk engine, execution firewall, live lock, release authority or broker credentials. Any future integration must be through narrow, read-only interfaces with explicit data minimization and independent review.

## Evidence limitations

This was README/metadata-level source triage only. No clone, build, install, container launch, code audit, dependency scan, penetration test or deployment was performed. No security or production-readiness certification is implied.
