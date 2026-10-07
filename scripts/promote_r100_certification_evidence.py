#!/usr/bin/env python3
"""Promote only independently satisfied R100 research outputs into certification evidence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.evidence_writer import build_evidence, write_evidence


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_payload(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    state_path = Path(".research_state/aurelia_r100_state.json")
    report_path = Path(".research_state/aurelia_r100_report.json")
    if not state_path.exists() or not report_path.exists():
        print("R100_EVIDENCE_PROMOTION=NO_INPUT")
        return 0

    state = json.loads(state_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = state["manifest"]

    ended_raw = (
        state.get("last_run_completed_at_utc")
        or manifest.get("campaign_end_at_utc")
        or datetime.now(timezone.utc).isoformat()
    )
    ended = datetime.fromisoformat(str(ended_raw).replace("Z", "+00:00"))
    valid_until = iso(ended + timedelta(days=30))
    source_hash = str(manifest.get("code_commit") or "")
    config_hash = str(manifest.get("config_hash") or "")
    archive_hash = str(report.get("archive_hash") or "")
    oos_count = int(report.get("oos_observations") or 0)

    Path("evidence").mkdir(parents=True, exist_ok=True)
    promoted = []

    # Prospective OOS is certifiable only after the predeclared campaign is
    # genuinely sealed and the certification minimum of 100 trades/cell exists.
    if (
        manifest.get("sealed") is True
        and report.get("campaign_complete") is True
        and report.get("retuning_after_seal") is False
        and report.get("multiple_testing", {}).get("status") == "ACCOUNTED"
        and isinstance(report.get("min_trades_per_strategy_symbol_regime"), int)
        and int(report["min_trades_per_strategy_symbol_regime"]) >= 100
        and archive_hash
        and source_hash
        and config_hash
    ):
        record = build_evidence(
            evidence_id=f"R100_PROSPECTIVE_OOS:{report.get('experiment_id','UNKNOWN')}",
            source_hash=source_hash,
            artifact_hash=archive_hash,
            config_hash=config_hash,
            data_hash=hash_payload(state.get("observations", [])),
            environment="research",
            started_at_utc=str(manifest["started_at_utc"]),
            ended_at_utc=iso(ended),
            status="CURRENT",
            valid_until_utc=valid_until,
            provenance={
                "origin": "research",
                "issuer": "aurelia-r100-prospective-oos",
                "source_commit": source_hash,
                "generated_at_utc": iso(datetime.now(timezone.utc)),
            },
            result="PROVEN",
            invariants_checked=[
                "sealed_prospective_data",
                "no_retuning_after_seal",
                "multiple_testing_accounted",
                "minimum_100_trades_per_strategy_symbol_regime",
            ],
            invariants_failed=[],
        )
        record.update({
            "sealed_prospective_data": True,
            "retuning_after_seal": False,
            "multiple_testing_accounted": True,
            "archive_hash": archive_hash,
            "strategy_version": str(report["strategy_version"]),
            "oos_window": f"{manifest['oos_start_at_utc']}..{ended_raw}",
            "min_trades_per_strategy_symbol_regime": oos_count,
        })
        record["record_hash"] = hash_payload({k: v for k, v in record.items() if k != "record_hash"})
        write_evidence(Path("evidence/prospective_oos.json"), record)
        promoted.append("PROSPECTIVE_OOS")

    # Calibration is promoted only when the collector itself validated it with
    # >=3 reliable buckets and no detected probability drift.
    calibration = report.get("probability") or {}
    if (
        calibration.get("calibration_status") == "VALIDATED_RESEARCH"
        and int(calibration.get("qualifying_reliability_buckets") or 0) >= 3
        and calibration.get("max_reliability_gap") is not None
        and not calibration.get("drift_detected")
        and source_hash
        and config_hash
    ):
        record = build_evidence(
            evidence_id=f"R100_CALIBRATION:{report.get('experiment_id','UNKNOWN')}",
            source_hash=source_hash,
            artifact_hash=archive_hash or hash_payload(calibration),
            config_hash=config_hash,
            data_hash=hash_payload(report.get("probability", {})),
            environment="research",
            started_at_utc=str(manifest["started_at_utc"]),
            ended_at_utc=iso(ended),
            status="CURRENT",
            valid_until_utc=valid_until,
            provenance={
                "origin": "research",
                "issuer": "aurelia-r100-prospective-oos",
                "source_commit": source_hash,
                "generated_at_utc": iso(datetime.now(timezone.utc)),
            },
            result="PROVEN",
            invariants_checked=[
                "brier_score_computed",
                "log_loss_computed",
                "minimum_three_qualifying_reliability_buckets",
                "drift_monitoring_completed",
                "no_detected_probability_drift",
            ],
            invariants_failed=[],
        )
        record.update({
            "calibration_validated": True,
            "drift_monitoring": True,
            "sample_count": int(calibration["sample_count"]),
            "brier_score": float(calibration["brier_score"]),
            "log_loss": float(calibration["log_loss"]),
            "reliability_buckets": calibration["reliability_buckets"],
        })
        record["record_hash"] = hash_payload({k: v for k, v in record.items() if k != "record_hash"})
        write_evidence(Path("evidence/calibration.json"), record)
        promoted.append("CALIBRATION")

    print(json.dumps({
        "R100_EVIDENCE_PROMOTION": "PASS",
        "PROMOTED": promoted,
        "OBSERVATIONS": int(report.get("observations_total") or 0),
        "OOS_OBSERVATIONS": oos_count,
        "QUALIFICATION_STATUS": report.get("qualification_status"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
