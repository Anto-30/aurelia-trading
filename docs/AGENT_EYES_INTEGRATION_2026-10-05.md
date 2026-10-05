# Agent Eyes Integration — 2026-10-05

AURELIA now tracks three external engineering tools as pinned, non-authoritative sources:

| Source | Pinned commit | AURELIA role |
|---|---|---|
| `kigiela/16-eyes` | `261d2b381b3ff6e819456d4c9aa40b9dff56b7d3` | security audit / adversarial finding verification |
| `DeHor-Labs/visual-eyes` | `c2ff5067353c6dbbcd09a4f0630147a042ba51e7` | visual UI and regression verification |
| `Touchpoint-Labs/Touchpoint` | `f512227621c3e0f4e5675e4e7dbed7aaebdcc76b` | desktop accessibility / MCP interaction tooling |

## Installation

Run:

`bash scripts/install_agent_eyes.sh`

The script performs pinned source checkout only. It does not execute third-party code, install production dependencies, access secrets, connect to Deriv, or change AURELIA capital controls.

The checkout destination is:

`.aurelia/external-tools/agent-eyes/`

The directory is intended for engineering/CI use and must not be imported into the capital or execution planes.

## Tool roles

### 16 Eyes

Use for full-repository and diff/PR security audits. It profiles the repository, creates tailored lenses, independently verifies findings, and adversarially reviews high-impact findings.

AURELIA use: assurance and security evidence only.

### Visual Eyes

Use for screenshot capture, visual inspection, responsive verification, and before/after visual regression checks for AURELIA web interfaces.

AURELIA use: engineering/UI verification only.

### Touchpoint

Use for structured desktop accessibility, native UI discovery, browser/Electron CDP access, and MCP-based agent interaction.

AURELIA use: engineering automation only. Any action-capable workflow must remain outside the capital plane and use explicit allowlists.

## Hard boundary

These sources do not receive:

- capital authority
- broker transaction-write authority
- Deriv credential access
- production secret access
- LIVE_LOCK mutation authority
- FINAL_EXECUTION_AUTHORIZATION authority
- strategy qualification authority
- live deployment authority

Their presence in the repository is not evidence of profitability, broker compatibility, strategy qualification, or live-trading readiness.

## Provenance

The pins are recorded in:

- `config/external_repo_federation.json`
- `config/agent_eyes_install_manifest.json`

The federation workflow remains responsible for reachability/head monitoring. Pin changes require an AURELIA review before adoption.

## Verification

After checkout, verify:

`git -C .aurelia/external-tools/agent-eyes/16-eyes rev-parse HEAD`

`git -C .aurelia/external-tools/agent-eyes/visual-eyes rev-parse HEAD`

`git -C .aurelia/external-tools/agent-eyes/Touchpoint rev-parse HEAD`

The output must exactly match the manifest pins.
