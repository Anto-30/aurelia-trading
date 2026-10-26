# Excluded External Sources

The following repositories are excluded from the approved dependency graph. This directory contains exclusion records only; no third-party source code is copied here.

- `composio-community/awesome-codex-skills`: no top-level LICENSE file found. Bulk installation, copying and redistribution are prohibited unless licensing is clarified and reviewed.
- `cline/prompts`: no top-level LICENSE file found. Its prompt content is untrusted and cannot enter the approved instruction or runtime graph.

Pinned provenance and reasons are recorded in `config/excluded_external_candidates.json`. Their presence in the historical federation inventory is for auditability, not dependency authorization. A future re-entry must be proposed as a new review with verified licensing, static analysis, isolated tests and independent human sign-off.
