from __future__ import annotations

"""Offline terminal sealing for an expired R_100 prospective campaign.

This module never connects to Deriv, never backfills data, and never re-scores
an existing campaign under a different source commit. It preserves the last
report as a historical snapshot and appends terminal archival metadata only.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from research.r100_prospective_oos_collector import (
    STATE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    iso,
    save_state,
    utc_now,
)


def _archive_hash(state: dict[str, Any]) -> str:
    payload = {
        "manifest": state["manifest"],
        "observations": state.get("observations", []),
        "quote_observations": state.get("quote_observations", []),
        "pending": state.get("pending", []),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_aware_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("R100_EXPIRY_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("R100_EXPIRY_TIMESTAMP_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("R100_EXPIRY_TIMESTAMP_INVALID")
    return parsed


def _assert_no_post_expiry_data(
    state: dict[str, Any],
    campaign_end: datetime,
) -> None:
    timestamp_fields = {
        "observations": ("signal_timestamp_utc", "exit_timestamp_utc"),
        "quote_observations": ("captured_at_utc",),
        "pending": ("signal_timestamp_utc",),
    }
    for collection, fields in timestamp_fields.items():
        rows = state.get(collection, [])
        if not isinstance(rows, list):
            raise ValueError("R100_ARCHIVE_COLLECTION_INVALID")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("R100_ARCHIVE_ROW_INVALID")
            for field in fields:
                timestamp = _parse_aware_timestamp(row.get(field))
                if timestamp >= campaign_end:
                    raise ValueError("R100_POST_EXPIRY_DATA_PRESENT")


def seal_expired_campaign(
    state_path: Path = STATE_PATH,
    *,
    now: datetime | None = None,
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

    sealed_at = now or utc_now()
    campaign_end = _parse_aware_timestamp(manifest.get("campaign_end_at_utc"))
    if sealed_at.tzinfo is None or sealed_at.utcoffset() is None:
        raise ValueError("R100_SEAL_TIMESTAMP_INVALID")
    if sealed_at < campaign_end:
        return {
            "status": "NOT_DUE",
            "sealed": False,
            "campaign_end_at_utc": manifest["campaign_end_at_utc"],
        }

    # Refuse to seal any snapshot containing an observation, exit, quote, or
    # pending signal timestamp at/after the immutable campaign cutoff.
    _assert_no_post_expiry_data(state, campaign_end)
    pending_count = len(state.get("pending", []))
    manifest["sealed"] = True
    manifest["sealed_at_utc"] = iso(sealed_at)
    manifest["seal_reason"] = "CAMPAIGN_WINDOW_ENDED"
    manifest["unresolved_pending_count"] = pending_count
    manifest["pending_resolution_status"] = (
        "UNRESOLVED_NO_BACKFILL" if pending_count else "RESOLVED"
    )
    archive_hash = _archive_hash(state)

    report_path = state_path.with_name("aurelia_r100_report.json")
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = {
            "schema": "aurelia.r100.prospective_oos.report.v1",
            "experiment_id": manifest.get("experiment_id"),
            "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION,
            "observations_total": len(state.get("observations", [])),
            "execution_economics": {"status": "UNDETERMINED_PRODUCTION"},
        }

    # Do not overwrite the historical metrics: they were calculated by the
    # campaign's frozen code. Explicitly mark them as the last collection
    # snapshot, not a new evaluation made by this sealer.
    report["last_collection_qualification_status"] = report.get(
        "qualification_status"
    )
    report["qualification_status"] = "NOT_RECALCULATED_AFTER_EXPIRY"
    report["evaluation_snapshot_status"] = "LAST_COLLECTION_SNAPSHOT_PRESERVED"
    report["sealing_note"] = (
        "Historical metrics were preserved unchanged. The sealer does not "
        "re-evaluate the frozen campaign under the current source code."
    )
    report["collection_status"] = "SEALED_AFTER_CAMPAIGN_WINDOW"
    report["campaign_complete"] = True
    report["campaign_terminal_status"] = (
        "SEALED_WITH_UNRESOLVED_PENDING" if pending_count else "SEALED"
    )
    report["pending_resolution_status"] = (
        "UNRESOLVED_NO_BACKFILL" if pending_count else "RESOLVED"
    )
    report["pending_count"] = pending_count
    report["archive_hash"] = archive_hash
    report["sealed_at_utc"] = manifest["sealed_at_utc"]
    report["retuning_after_seal"] = False
    report["strategy_live_eligible"] = False
    report["execution_authorized"] = False
    report["capital_authority"] = False
    report["live_execution"] = False

    report_temp = report_path.with_suffix(report_path.suffix + ".tmp")
    report_temp.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    report_temp.replace(report_path)
    save_state(state_path, state)

    return {
        "status": "SEALED_WITH_UNRESOLVED_PENDING" if pending_count else "SEALED",
        "sealed": True,
        "experiment_id": manifest.get("experiment_id"),
        "observations_total": len(state.get("observations", [])),
        "pending_count": pending_count,
        "pending_resolution_status": report["pending_resolution_status"],
        "qualification_status": report["qualification_status"],
        "archive_hash": archive_hash,
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
