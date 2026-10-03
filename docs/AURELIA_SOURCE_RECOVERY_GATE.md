# AURELIA Source Recovery Gate

Date: 2026-10-03

## Purpose

This gate records the evidence needed to recover the real AURELIA implementation before any implementation-level certification work is claimed.

## Historical source reference

The connected Notion workspace contains a page titled **Aurelia trading systems** that records a packaged release:

- `Aurelia_Autonomous_MultiAgent_Build_v1.27.zip`
- `aurelia-v1.27-safe.zip`
- Recorded release date: 2026-09-20
- Recorded source-of-truth status: the v1.27-safe package
- Recorded test result: 93 passed / 0 failed
- Recorded live lock: `LIVE_LOCK.yaml` with `live_trading_enabled: false`
- Recorded broker adapter: `services/adapters/deriv_adapter.py`
- Recorded validation module: `services/validation/walk_forward.py`

The Notion record is evidence that the package was documented as existing; it is **not the package itself** and is not sufficient for implementation verification.

## Recovery searches completed on 2026-10-03

### Connected storage / workspace

- ChatGPT conversation Files/Library: no authoritative AURELIA source archive or source tree recovered.
- Dropbox: no matches for the v1.27 archive names, `LIVE_LOCK.yaml`, `deriv_adapter.py`, `TEST_RESULTS.md`, or AURELIA source terms.
- Notion: historical reference page recovered; no source attachment/package exposed by that page.
- Remote Desktop Commander: no development devices connected.
- Railway: project `AURELIA-Production-Worker` exists; production currently has zero services.

### GitHub

Accessible repositories owned by `Anto-30` that match AURELIA naming:

- `Anto-30/aurelia-trading`: assurance plane only; current branch contains the production-evidence framework, not the historical AURELIA runtime.
- `Anto-30/Aurelia-trading-`: only `README.md` is present; initial commit only.

Additional GitHub repository/commit searches for the historical archive names and distinctive source paths produced no recoverable AURELIA v1.27 source.

### Public web

Exact-name searches for the two historical v1.27 archives and distinctive AURELIA implementation identifiers produced no public source artifact.

## Current conclusion

The authoritative AURELIA runtime is **not currently accessible** through the connected execution routes.

Therefore:

- implementation-level repairs cannot be honestly completed;
- implementation-level tests cannot be run;
- broker lifecycle proof cannot be completed;
- the 3600-second adversarial soak cannot be run against the real engine;
- multi-day OOS and calibration cannot be rerun against the authoritative strategy implementation;
- deployment/runtime integrity cannot be certified for the real engine.

The assurance branch must remain fail-closed.

## Required recovery artifact

At least one of these must become accessible:

1. The complete v1.27-safe source archive.
2. A complete source-tree export of the current AURELIA runtime.
3. A connected development machine containing the authoritative source tree.
4. A synchronized Git repository containing the authoritative source.

## Integrity checks after recovery

Before modifying recovered code:

1. Record archive/tree hash.
2. Record source commit if applicable.
3. Record release/version identifier.
4. Preserve the original source unchanged.
5. Create an isolated engineering branch.
6. Inventory execution-capable modules and broker credentials.
7. Compare implementation against the assurance contracts.
8. Run the existing test suite before modifications.
9. Continue only with evidence-backed repairs and validation.

## Capital safety

This recovery gate never authorizes trading.

`FINAL_EXECUTION_AUTHORIZATION = FALSE`

`LIVE_EXECUTION_ALLOWED = FALSE`

`LIVE_ORDERS = 0`

No missing source may be reconstructed by guessing, and no documentation-only artifact may be promoted to production evidence.
