# AURELIA Source Recovery Gate

Date: 2026-10-03

## Purpose

This gate records the evidence needed to recover the real AURELIA implementation before any implementation-level certification work is claimed.

## Recovered source reference

The connected Notion workspace contains a page titled **Aurelia trading systems** that records a packaged release:

- `Aurelia_Autonomous_MultiAgent_Build_v1.27.zip`
- `aurelia-v1.27-safe.zip`
- Recorded release date: 2026-09-20
- Recorded source-of-truth status: the v1.27-safe package
- Recorded test result: 93 passed / 0 failed
- Recorded live lock: `LIVE_LOCK.yaml` with `live_trading_enabled: false`
- Recorded broker adapter: `services/adapters/deriv_adapter.py`
- Recorded validation module: `services/validation/walk_forward.py`

The Notion record is evidence that the package existed; it is **not the package itself** and is not sufficient for implementation verification.

## Searches performed

The currently connected environment was searched for:

- AURELIA source code
- `Aurelia_Autonomous_MultiAgent_Build_v1.27.zip`
- `aurelia-v1.27-safe.zip`
- `services/adapters/deriv_adapter.py`
- `services/validation/walk_forward.py`
- `LIVE_LOCK.yaml`
- `MICRO_SCALP_R100_TICK_MOM_v0.1.0`
- Risk Warden
- Execution Firewall
- `/home/workdir/artifacts`

No source archive or source tree was recovered from the connected Files/Library, Dropbox, or GitHub repositories.

## Current GitHub state

Repository: `Anto-30/aurelia-trading`

The assurance branch contains the production-evidence framework, but the actual AURELIA implementation is not present.

Therefore the certification gate must remain fail-closed.

## Required recovery artifact

One of the following must become accessible:

1. The complete v1.27-safe source archive.
2. A complete source-tree export of the current AURELIA runtime.
3. A connected development machine containing the authoritative source tree.
4. A synchronized Git repository containing the authoritative source.

## Required integrity checks after recovery

Before modifying recovered code:

1. Record archive/tree hash.
2. Record source commit if applicable.
3. Record release/version identifier.
4. Preserve the original source unchanged.
5. Create an isolated engineering branch.
6. Inventory execution-capable modules.
7. Compare recovered implementation against the current assurance contracts.
8. Run the existing test suite before modifications.
9. Only then repair implementation gaps.

## Capital safety

This recovery gate does not authorize trading.

`FINAL_EXECUTION_AUTHORIZATION = FALSE`

`LIVE_EXECUTION_ALLOWED = FALSE`

`LIVE_ORDERS = 0`

No missing source may be reconstructed by guessing, and no documentation-only artifact may be promoted to production evidence.
