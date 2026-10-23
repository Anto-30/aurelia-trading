# External repository intake — ATOS v2.0 / AURELIA

**Decision: selective reference only; no external repository is approved for wholesale copy, runtime import, or production deployment.** The AURELIA canonical control plane, deterministic Layer 6 risk authority, ledger/reconciliation and release firewall remain authoritative. Third-party projects are development-time references unless a later architecture review approves a narrow adapter.

Review date: 2026-10-22. Repository names, declared licenses, branches and descriptions below were retrieved from GitHub repository metadata and public READMEs. This is an intake triage, not a complete code audit, dependency/SBOM scan, legal opinion, or security certification. Recheck license files, dependency licenses, current commit, maintenance state and threat model before copying or deploying any code.

## Decision summary

| Repository | Declared license | Fit for AURELIA | Decision |
|---|---|---|---|
| [zackb/tether](https://github.com/zackb/tether) | MIT | Bridges iPhone Continuity/iMessage/SMS and a Linux Wayland desktop. Not an Android/WhatsApp Cloud API notification path. | **Reject for current scope.** Revisit only for a separate Linux+iPhone desktop integration. Treat messages, contacts and notifications as sensitive data. |
| [Genymobile/gnirehtet](https://github.com/Genymobile/gnirehtet) | Apache-2.0 | Android reverse tethering over ADB; could help a controlled device-lab connectivity scenario, but not strategy validation or notification delivery. README says the project is not actively maintained except major blockers. | **Do not integrate.** At most use as an isolated lab utility after testing Android version compatibility and reviewing its network/ADB permissions. |
| [remsky/Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) | Apache-2.0 repository metadata | Dockerized Kokoro TTS service with an OpenAI-compatible API. Could turn existing status notifications into optional spoken summaries, but it adds model/runtime/GPU or CPU load and separate model/weight licenses must be checked. | **Optional future sidecar only.** Do not connect it to order authorization or risk decisions. No present blocker depends on TTS. |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | MIT | Python HTTP/API framework; consistent with the existing Python backend direction. | **Approved as a framework reference/dependency where already justified**, not as an extra competing application or trading engine. Keep API routes read-only for research telemetry. |
| [FastEndpoints/FastEndpoints](https://github.com/FastEndpoints/FastEndpoints) | MIT | ASP.NET/C# REST framework, not compatible with AURELIA's Python service stack without introducing a second application runtime. | **Reject for this project.** Reconsider only if a separate .NET service is explicitly approved with a clear service boundary. |
| [Aeternalis-Ingenium/FastAPI-Backend-Template](https://github.com/Aeternalis-Ingenium/FastAPI-Backend-Template) | GPL-3.0 | FastAPI, PostgreSQL, async SQLAlchemy, Alembic and Docker template. Technically relevant patterns, but a copyleft license is a material adoption constraint and the template duplicates current project infrastructure. | **Do not copy into the canonical repository without legal review.** Learn from architecture patterns only; prefer project-owned implementation. |
| [preactjs/preact](https://github.com/preactjs/preact) | MIT | Lightweight JS UI library. Could build a compact read-only operator dashboard. | **No current adoption.** Existing product direction already contemplates a Next.js/TypeScript UI; do not introduce a second frontend stack without a deliberate choice. |
| [PipedreamHQ/pipedream](https://github.com/PipedreamHQ/pipedream) | GitHub API reported NOASSERTION | Workflow/integration platform that could connect APIs and notifications. Repository-level licensing could not be confidently established from that metadata. It is also a hosted-platform dependency, not a core trading component. | **Do not vendor/deploy from source until its applicable license and terms are verified.** Prefer the existing notification boundary and self-hosted workflow option where appropriate. Do not allow workflows to authorize trades. |
| [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate) | MIT | Async FastAPI/Pydantic v2/SQLAlchemy/PostgreSQL/Redis boilerplate with jobs, caching and rate-limits. Most relevant backend reference in this list. | **Reference-only; highest-priority codebase for a later focused architecture comparison.** Do not replace AURELIA's ledger, capital plane, risk engine or release gates with boilerplate modules. Select components only after a dependency and security review. |
| [insistence/RuoYi-FastAPI](https://github.com/insistence/RuoYi-FastAPI) | MIT | Broad admin backend/frontend with Vue/React and code generation. Could provide UI patterns for a future control/observability console. | **Do not import wholesale.** Prefer a small read-only dashboard against an explicit API; scrutinize default credentials, permissions, migrations, code generators and exposed admin routes before any limited reuse. |

## Integration constraints

1. **One canonical authority.** None of these repositories may create another capital manager, risk engine, order-execution path, strategy registry, or reconciliation ledger. Agents and third-party workflows may suggest or report; they cannot independently authorize capital actions.
2. **Development-time intake first.** Pin exact commit SHAs, record licenses and transitive dependencies, inspect install/build scripts, run static analysis and tests in a sandbox, and produce an SBOM before proposing a runtime dependency. Do not run arbitrary third-party install scripts on an authenticated trading host.
3. **Data and notification isolation.** For the current MSNR effort, use the Deriv unauthenticated public market-data WebSocket only. TTS, dashboard, automation and device utilities are non-critical read-only consumers; their failures must not change risk decisions or bypass gates.
4. **No secrets in source.** PATs, OAuth credentials, OTP URLs, app secrets and account IDs must not be committed, pasted into logs, or copied into test fixtures. This intake used public GitHub metadata/READMEs only; it did not use any Deriv credentials.
5. **Licensing is a gate.** Repository license metadata is not enough to certify every dependency or model asset. In particular, perform counsel review before incorporating GPL-3.0 template code, and do not assume Pipedream source is open-source merely because it is public.
6. **No automatic merge.** The recommendations are not evidence of production readiness. Any future implementation requires a separate scoped PR, exact-base review, tests, dependency/security scan, independent review and preserved config/LIVE_LOCK.yaml state.

## Immediate plan

- Keep the MSNR public fetcher, strict data verifier, frozen simulator, and metrics ledger in the isolated research directory.
- Add a public-only Deriv client for active_symbols, ticks_history, and ticks; explicitly reject auth/account/order fields. The client does not implement PAT/OTP or buy/sell calls.
- Use FastAPI only if a read-only research/status API is needed. Defer Kokoro voice summaries, Preact, FastEndpoints, device-tether utilities, and broad admin-boilerplate reuse.
- Keep Pipedream source out of the tree until licensing and operational dependency requirements are resolved.

## Sources

- Tether: https://github.com/zackb/tether
- Gnirehtet: https://github.com/Genymobile/gnirehtet
- Kokoro-FastAPI: https://github.com/remsky/Kokoro-FastAPI
- FastAPI: https://github.com/fastapi/fastapi
- FastEndpoints: https://github.com/FastEndpoints/FastEndpoints
- FastAPI Backend Template: https://github.com/Aeternalis-Ingenium/FastAPI-Backend-Template
- Preact: https://github.com/preactjs/preact
- Pipedream: https://github.com/PipedreamHQ/pipedream
- FastAPI Boilerplate: https://github.com/benavlabs/FastAPI-boilerplate
- RuoYi-FastAPI: https://github.com/insistence/RuoYi-FastAPI
