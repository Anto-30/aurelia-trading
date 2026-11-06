from __future__ import annotations

"""Offline terminal sealing for an expired R_100 prospective campaign.

This module never connects to Deriv, never backfills data, and never changes
strategy parameters. It freezes the original state and explicitly preserves
any unresolved pending signals.
"""

import json
import os
from pathlib import Path
from typing import Any

from research.r100_prospective_oos_collector import (
    STATE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    evaluation,
    iso,
    save_state,
    utc_now,
)


def seal_expired_campaign(
    state_path: Path = STATE_PATH,
    *,
    now=None,
) -> dict[str, Any]:
    if not state_path.exists():
        return {"status": "NO_STATE", "sealed": False}

    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("schema") != "aurelia.r100.prospective_oos.v1":
        raise ValueError("R100_STATE_SCHEMA_MISMATCH")
    manifest = state.get("manifest") or {}
    if manifest.get("strategy_id") != STRATEGY_ID:
        raise ValueError("R100_STRATEGY_MISMATCH")
    if manifest.get("strategy_version") != STRATEGY_VERSION:
        raise ValueError("R100_STRATEGY_VERSION_MISMATCH")
    if manifest.get("sealed"):
        return {
            "status": "ALREADY_SEALED",
            "sealed": True,
            "experiment_id": manifest.get("experiment_id"),
        }

    evaluated_at = now or utc_now()
    campaign_end = __import__("datetime").datetime.fromisoformat(
        manifest["campaign_end_at_utc"].replace("Z", "+00:00")
    )
    if evaluated_at < campaign_end:
        return {
            "status": "NOT_DUE",
            "sealed": False,
            "campaign_end_at_utc": manifest["campaign_end_at_utc"],
        }

    report = evaluation(state, now=evaluated_at)
    pending_count = len(state.get("pending", []))
    report["collection_status"] = "SEALED_AFTER_CAMPAIGN_WINDOW"
    report["pending_resolution_status"] = (
        "UNRESOLVED_NO_BACKFILL" if pending_count else "RESOLVED"
    )
    report["pending_count"] = pending_count
    report["collection_error_type"] = state.get("last_run_error_type")
    report["collection_error_code"] = state.get("last_run_error_code")

    save_state(state_path, state)
    report_path = state_path.with_name("aurelia_r100_report.json")
    temp = report_path.with_suffix(report_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    temp.replace(report_path)
    return {
        "status": "SEALED_WITH_UNRESOLVED_PENDING" if pending_count else "SEALED",
        "sealed": True,
        "experiment_id": manifest.get("experiment_id"),
        "observations_total": report["observations_total"],
        "oos_observations": report["oos_observations"],
        "pending_count": pending_count,
        "pending_resolution_status": report["pending_resolution_status"],
        "qualification_status": report["qualification_status"],
        "archive_hash": report["archive_hash"],
        "report_path": str(report_path),
    }


def main() -> int:
    result = seal_expired_campaign(
        Path(os.getenv("AURELIA_R100_STATE_PATH", str(STATE_PATH)))
    )
    print(json.dumps({"R100_CAMPAIGN_EXPIRY": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
