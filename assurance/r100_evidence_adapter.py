"""Adapt a genuinely sealed R100 research campaign into certification evidence.

This adapter is read-only with respect to the broker and writes evidence only
when source, campaign seal, archive hash, OOS sample, and calibration all verify.
It never manufactures execution-economics, deployment, broker, recovery, or soak
evidence.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import pathlib

import assurance.evidence_writer


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: object) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _parse_utc(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("R100_EVIDENCE_TIMESTAMP_MUST_BE_AWARE")
    return parsed.astimezone(datetime.timezone.utc)


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _same_number(left: object, right: object) -> bool:
    return _finite(left) and _finite(right) and math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-12)


def _recompute_data_coverage(
    windows: list[dict],
    oos_start: datetime.datetime,
    campaign_end: datetime.datetime,
) -> dict:
    if not isinstance(windows, list):
        raise ValueError("R100_DATA_WINDOWS_INVALID")
    total_seconds = (campaign_end - oos_start).total_seconds()
    if total_seconds <= 0:
        raise ValueError("R100_CAMPAIGN_WINDOW_INVALID")
    intervals = []
    max_tick_gap_seconds = 0.0
    for window in windows:
        if not isinstance(window, dict):
            raise ValueError("R100_DATA_WINDOW_RECORD_INVALID")
        count = window.get("tick_count")
        if type(count) is not int or count < 0:
            raise ValueError("R100_DATA_WINDOW_TICK_COUNT_INVALID")
        try:
            run_start = _parse_utc(window["run_started_at_utc"])
            run_end = _parse_utc(window["run_completed_at_utc"])
            tick_gap = window["max_tick_gap_seconds"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("R100_DATA_WINDOW_TIMESTAMP_OR_GAP_INVALID") from exc
        if run_end <= run_start:
            raise ValueError("R100_DATA_WINDOW_RUN_INTERVAL_INVALID")
        if not _finite(tick_gap) or float(tick_gap) < 0:
            raise ValueError("R100_DATA_WINDOW_TICK_GAP_INVALID")
        tick_gap = float(tick_gap)
        first_raw, last_raw = window.get("first_tick_at_utc"), window.get("last_tick_at_utc")
        if count == 0:
            if first_raw is not None or last_raw is not None or tick_gap != 0:
                raise ValueError("R100_EMPTY_DATA_WINDOW_CONTRADICTORY")
            continue
        if first_raw is None or last_raw is None:
            raise ValueError("R100_DATA_WINDOW_TICK_BOUNDARY_MISSING")
        try:
            first, last = _parse_utc(first_raw), _parse_utc(last_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("R100_DATA_WINDOW_TICK_TIMESTAMP_INVALID") from exc
        # Deriv tick epochs have one-second precision; a tick timestamp can
        # floor into the second immediately before the local collection start,
        # or equal the local completion second. Allow only that one-second
        # representation tolerance; it does not add measurable coverage.
        if (
            first < run_start - datetime.timedelta(seconds=1)
            or last > run_end + datetime.timedelta(seconds=1)
            or last < first
        ):
            raise ValueError("R100_DATA_WINDOW_TICK_TIME_OUTSIDE_RUN")
        if count == 1:
            if first != last or tick_gap != 0:
                raise ValueError("R100_SINGLE_TICK_WINDOW_CONTRADICTORY")
            if first >= campaign_end:
                raise ValueError("R100_POST_EXPIRY_TICK_DATA_PRESENT")
            continue
        if last < first:
            raise ValueError("R100_DATA_WINDOW_TICK_ORDER_INVALID")
        if last >= campaign_end:
            raise ValueError("R100_POST_EXPIRY_TICK_DATA_PRESENT")
        max_tick_gap_seconds = max(max_tick_gap_seconds, tick_gap)
        if last == first:
            if tick_gap != 0:
                raise ValueError("R100_SAME_SECOND_TICK_GAP_CONTRADICTORY")
            # Multiple feed events may share a second-resolution epoch. They
            # remain valid observations but contribute no time-coverage span.
            continue
        clipped_start, clipped_end = max(first, oos_start), min(last, campaign_end)
        if clipped_end > clipped_start:
            intervals.append((clipped_start, clipped_end))
    intervals.sort(key=lambda item: item[0])
    merged = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    covered = sum((end - start).total_seconds() for start, end in merged)
    cursor, gaps = oos_start, []
    for start, end in merged:
        gaps.append(max(0.0, (start - cursor).total_seconds()))
        cursor = max(cursor, end)
    gaps.append(max(0.0, (campaign_end - cursor).total_seconds()))
    max_gap = max(gaps) if gaps else total_seconds
    fraction = covered / total_seconds
    valid = len(merged) >= 24 and fraction >= 0.50 and max_gap <= 1800 and max_tick_gap_seconds <= 30
    return {
        "collection_window_count": len(merged),
        "covered_seconds": covered,
        "oos_window_seconds": total_seconds,
        "data_coverage_fraction": fraction,
        "max_observation_gap_seconds": max_gap,
        "max_tick_gap_seconds": max_tick_gap_seconds,
        "data_coverage_valid": valid,
    }


def _recompute_probability_metrics(rows: list[dict]) -> dict:
    if not isinstance(rows, list) or not rows:
        raise ValueError("R100_EVIDENCE_OOS_OBSERVATIONS_EMPTY")
    probabilities, outcomes = [], []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("R100_EVIDENCE_OOS_ROW_INVALID")
        p, y = row.get("probability"), row.get("outcome")
        if not _finite(p):
            raise ValueError("R100_EVIDENCE_PROBABILITY_INVALID")
        if type(y) is not int or y not in (0, 1):
            raise ValueError("R100_EVIDENCE_OUTCOME_INVALID")
        probabilities.append(float(p))
        outcomes.append(y)
    if any(not 0.55 <= p <= 0.75 for p in probabilities):
        raise ValueError("R100_EVIDENCE_PROBABILITY_OUT_OF_POLICY")
    brier = sum((p-y)**2 for p,y in zip(probabilities,outcomes))/len(rows)
    log_loss = 0.0
    for p,y in zip(probabilities,outcomes):
        clipped=min(1.0-1e-12,max(1e-12,p))
        log_loss += -(y*math.log(clipped)+(1-y)*math.log(1-clipped))
    log_loss /= len(rows)
    edges=[0.55,0.60,0.65,0.70,0.75+1e-12]
    buckets=[]
    for lower,upper in zip(edges,edges[1:]):
        samples=[(p,y) for p,y in zip(probabilities,outcomes) if lower<=p<upper]
        if samples:
            buckets.append({"lower":lower,"upper":upper,"count":len(samples),
                "mean_probability":sum(p for p,_ in samples)/len(samples),
                "realized_rate":sum(y for _,y in samples)/len(samples)})
    qualifying=[b for b in buckets if b["count"]>=10]
    gaps=[abs(b["mean_probability"]-b["realized_rate"]) for b in qualifying]
    midpoint=max(1,len(probabilities)//2)
    baseline=sum(probabilities[:midpoint])/midpoint
    recent=sum(probabilities[midpoint:])/max(1,len(probabilities)-midpoint)
    drift=abs(baseline-recent)>0.05
    status="VALIDATED_RESEARCH" if len(rows)>=100 and len(qualifying)>=3 and gaps and max(gaps)<=0.05 and not drift else "PROVISIONAL"
    return {"sample_count":len(rows),"brier_score":brier,"log_loss":log_loss,
        "reliability_buckets":buckets,"qualifying_reliability_buckets":len(qualifying),
        "max_reliability_gap":max(gaps) if gaps else None,"drift_detected":drift,
        "calibration_status":status}


def _build_record(
    *,
    evidence_id: str,
    source_commit: str,
    config_hash: str,
    archive_hash: str,
    artifact_hash: str,
    started_at: str,
    ended_at: str,
    generated_at: str,
    issuer: str,
    domain_fields: dict,
    invariants: list[str],
) -> dict:
    record = assurance.evidence_writer.build_evidence(
        evidence_id=evidence_id,
        source_hash=source_commit,
        artifact_hash=artifact_hash,
        config_hash=config_hash,
        data_hash=archive_hash,
        environment="research",
        started_at_utc=started_at,
        ended_at_utc=ended_at,
        status="CURRENT",
        result="VALIDATED",
        provenance={
            "origin": "research",
            "issuer": issuer,
            "source_commit": source_commit,
            "generated_at_utc": generated_at,
        },
        invariants_checked=invariants,
        invariants_failed=[],
    )
    record.update(domain_fields)
    record.pop("record_hash", None)
    record["record_hash"] = assurance.evidence_writer.payload_sha256(record)
    return record


def adapt_sealed_campaign(
    state: dict,
    report: dict,
    *,
    state_bytes: bytes,
    report_bytes: bytes,
    generated_at: str | None = None,
) -> dict[str, dict]:
    manifest = state.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("R100_EVIDENCE_MANIFEST_MISSING")
    if state.get("schema") != "aurelia.r100.prospective_oos.v1":
        raise ValueError("R100_EVIDENCE_STATE_SCHEMA_INVALID")
    if report.get("schema") != "aurelia.r100.prospective_oos.report.v1":
        raise ValueError("R100_EVIDENCE_REPORT_SCHEMA_INVALID")
    if manifest.get("sealed") is not True or report.get("campaign_complete") is not True:
        raise ValueError("R100_CAMPAIGN_NOT_SEALED")
    if state.get("pending"):
        raise ValueError("R100_PENDING_SIGNALS_REMAIN")
    if report.get("collection_status") != "PASS":
        raise ValueError("R100_COLLECTION_NOT_PASS")
    if report.get("retuning_after_seal") is not False:
        raise ValueError("R100_RETUNING_AFTER_SEAL_NOT_EXCLUDED")

    source_commit = str(manifest.get("code_commit") or "")
    config_hash = str(manifest.get("config_hash") or "")
    if len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise ValueError("R100_SOURCE_COMMIT_NOT_PINNED")
    if len(config_hash) != 64 or any(char not in "0123456789abcdef" for char in config_hash):
        raise ValueError("R100_CONFIG_HASH_NOT_PINNED")

    censored = state.get("censored_signals", [])
    if not isinstance(censored, list):
        raise ValueError("R100_CENSORED_SIGNALS_INVALID")
    expected_archive_hash = _canonical_hash({
        "manifest": manifest,
        "observations": state.get("observations", []),
        "quote_observations": state.get("quote_observations", []),
        "censored_signals": censored,
    })
    archive_hash = str(report.get("archive_hash") or "")
    if archive_hash != expected_archive_hash:
        raise ValueError("R100_ARCHIVE_HASH_MISMATCH")
    if len(archive_hash) != 64:
        raise ValueError("R100_ARCHIVE_HASH_INVALID")

    strategy_id = manifest.get("strategy_id")
    if strategy_id != "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0" or manifest.get("strategy_version") != "0.2.0":
        raise ValueError("R100_STRATEGY_IDENTITY_INVALID")
    producer = manifest.get("producer")
    if not isinstance(producer, dict):
        raise ValueError("R100_CAMPAIGN_PRODUCER_MISSING")
    run_id, workflow_id, head_sha = producer.get("workflow_run_id"), producer.get("workflow_id"), producer.get("head_sha")
    if (
        not isinstance(run_id, str) or not run_id.isdigit()
        or not isinstance(workflow_id, str) or not workflow_id.isdigit()
        or producer.get("workflow_path") != ".github/workflows/r100-prospective-oos.yml"
        or producer.get("head_branch") != "main"
        or producer.get("event") not in {"push", "schedule", "workflow_dispatch"}
        or not isinstance(head_sha, str) or len(head_sha) != 40
        or any(ch not in "0123456789abcdef" for ch in head_sha)
        or head_sha != source_commit
    ):
        raise ValueError("R100_CAMPAIGN_PRODUCER_INVALID")
    observations = state.get("observations")
    if not isinstance(observations, list):
        raise ValueError("R100_OBSERVATIONS_INVALID")
    quotes = state.get("quote_observations")
    if not isinstance(quotes, list):
        raise ValueError("R100_QUOTE_OBSERVATIONS_INVALID")
    campaign_start = _parse_utc(str(manifest["started_at_utc"]))
    oos_start = _parse_utc(str(manifest["oos_start_at_utc"]))
    campaign_end = _parse_utc(str(manifest["campaign_end_at_utc"]))
    if not campaign_start <= oos_start < campaign_end:
        raise ValueError("R100_CAMPAIGN_WINDOW_INVALID")
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("R100_OBSERVATION_ROW_INVALID")
        if (
            row.get("strategy_id") != strategy_id
            or row.get("strategy_version") != manifest["strategy_version"]
            or row.get("symbol") != "R_100"
            or row.get("regime") != "ALL_MARKET"
        ):
            raise ValueError("R100_OBSERVATION_STRATEGY_CELL_MISMATCH")
        signal = _parse_utc(str(row.get("signal_timestamp_utc", "")))
        exit_time = _parse_utc(str(row.get("exit_timestamp_utc", "")))
        if signal < campaign_start or signal >= campaign_end or exit_time < signal or exit_time >= campaign_end:
            raise ValueError("R100_POST_EXPIRY_DATA_PRESENT")
        if not _finite(row.get("raw_return")) or row.get("direction") not in {"CALL", "PUT"}:
            raise ValueError("R100_OOS_RETURN_INVALID")
    for item in censored:
        if not isinstance(item, dict):
            raise ValueError("R100_CENSORED_SIGNAL_INVALID")
        if (
            item.get("strategy_id") != strategy_id
            or item.get("strategy_version") != manifest["strategy_version"]
            or item.get("symbol") != "R_100"
            or item.get("regime") != "ALL_MARKET"
            or item.get("censor_reason") != "HORIZON_NOT_REACHED_BEFORE_CAMPAIGN_CUTOFF"
        ):
            raise ValueError("R100_CENSORED_SIGNAL_IDENTITY_INVALID")
        signal_time = _parse_utc(str(item.get("signal_timestamp_utc", "")))
        censored_time = _parse_utc(str(item.get("censored_at_utc", "")))
        if signal_time < campaign_start or signal_time >= campaign_end or censored_time != campaign_end:
            raise ValueError("R100_CENSORED_SIGNAL_CUTOFF_INVALID")
        if item.get("direction") not in {"CALL", "PUT"} or not _finite(item.get("probability")):
            raise ValueError("R100_CENSORED_SIGNAL_FIELDS_INVALID")
        if not 0.55 <= float(item["probability"]) <= 0.75:
            raise ValueError("R100_CENSORED_SIGNAL_PROBABILITY_INVALID")
        if type(item.get("horizon_ticks")) is not int or item["horizon_ticks"] < 1:
            raise ValueError("R100_CENSORED_SIGNAL_HORIZON_INVALID")
        if type(item.get("age_ticks")) is not int or item["age_ticks"] < 0 or item["age_ticks"] >= item["horizon_ticks"]:
            raise ValueError("R100_CENSORED_SIGNAL_AGE_INVALID")
        if not _finite(item.get("score")):
            raise ValueError("R100_CENSORED_SIGNAL_SCORE_INVALID")
        if any(key in item for key in ("outcome", "raw_return", "exit_timestamp_utc")):
            raise ValueError("R100_CENSORED_SIGNAL_MUST_NOT_CARRY_OUTCOME")

    if type(report.get("censored_signal_count")) is not int or report["censored_signal_count"] != len(censored):
        raise ValueError("R100_CENSORED_SIGNAL_COUNT_MISMATCH")

    for quote in quotes:
        if not isinstance(quote, dict):
            raise ValueError("R100_QUOTE_OBSERVATION_INVALID")
        captured = _parse_utc(str(quote.get("captured_at_utc", "")))
        if captured < campaign_start or captured >= campaign_end:
            raise ValueError("R100_POST_EXPIRY_DATA_PRESENT")
        if quote.get("quote_status") not in {"OBSERVED", "UNAVAILABLE"}:
            raise ValueError("R100_QUOTE_STATUS_INVALID")
        if quote.get("quote_status") == "OBSERVED" and (
            not _finite(quote.get("ask_price")) or float(quote["ask_price"]) <= 0
            or not _finite(quote.get("payout")) or float(quote["payout"]) <= 0
        ):
            raise ValueError("R100_QUOTE_ECONOMICS_INVALID")
    oos_rows = [row for row in observations if _parse_utc(str(row["signal_timestamp_utc"])) >= oos_start]
    if type(report.get("oos_observations")) is not int or len(oos_rows) != report["oos_observations"]:
        raise ValueError("R100_OOS_SAMPLE_COUNT_MISMATCH")
    if type(report.get("observations_total")) is not int or len(observations) != report["observations_total"]:
        raise ValueError("R100_TOTAL_SAMPLE_COUNT_MISMATCH")
    if len(oos_rows) < 100:
        raise ValueError("R100_OOS_SAMPLE_LT_100")
    recomputed_coverage = _recompute_data_coverage(
        manifest.get("data_windows", []),
        oos_start,
        campaign_end,
    )
    reported_coverage = report.get("data_coverage")
    if not isinstance(reported_coverage, dict):
        raise ValueError("R100_DATA_COVERAGE_REPORT_MISSING")
    for key, expected in recomputed_coverage.items():
        actual = reported_coverage.get(key)
        if isinstance(expected, float):
            if not _same_number(actual, expected):
                raise ValueError(f"R100_DATA_COVERAGE_{key.upper()}_MISMATCH")
        elif actual != expected:
            raise ValueError(f"R100_DATA_COVERAGE_{key.upper()}_MISMATCH")
    for key in (
        "data_coverage_valid",
        "data_coverage_fraction",
        "max_observation_gap_seconds",
        "collection_window_count",
    ):
        if report.get(key) != recomputed_coverage.get(key):
            if not (_finite(report.get(key)) and _same_number(
                report.get(key), recomputed_coverage.get(key)
            )):
                raise ValueError(f"R100_DATA_COVERAGE_SUMMARY_{key.upper()}_MISMATCH")
    if not recomputed_coverage["data_coverage_valid"]:
        raise ValueError("R100_OOS_DATA_COVERAGE_INCOMPLETE")

    returns = []
    for row in oos_rows:
        raw_return = float(row["raw_return"])
        direction = row["direction"]
        if not math.isfinite(raw_return) or direction not in {"CALL", "PUT"}:
            raise ValueError("R100_OOS_RETURN_INVALID")
        returns.append(raw_return if direction == "CALL" else -raw_return)
    mean_return = sum(returns) / len(returns)
    if not _same_number(mean_return, report.get("oos_mean_strategy_return")):
        raise ValueError("R100_OOS_EXPECTANCY_RECOMPUTE_MISMATCH")
    if mean_return <= 0:
        raise ValueError("R100_OOS_EXPECTANCY_NOT_POSITIVE")

    multiple_testing = report.get("multiple_testing")
    if not isinstance(multiple_testing, dict) or multiple_testing.get("status") != "ACCOUNTED":
        raise ValueError("R100_MULTIPLE_TESTING_NOT_ACCOUNTED")
    trial_count = multiple_testing.get("trial_count")
    reuse_count = multiple_testing.get("oos_reuse_count")
    if not isinstance(trial_count, int) or isinstance(trial_count, bool) or trial_count < 1:
        raise ValueError("R100_TRIAL_COUNT_INVALID")
    if not isinstance(reuse_count, int) or isinstance(reuse_count, bool) or reuse_count < 0:
        raise ValueError("R100_OOS_REUSE_COUNT_INVALID")

    probability_report = report.get("probability")
    recalculated = _recompute_probability_metrics(oos_rows)
    if not isinstance(probability_report, dict):
        raise ValueError("R100_CALIBRATION_REPORT_MISSING")
    for key in ("sample_count", "calibration_status", "drift_detected", "qualifying_reliability_buckets"):
        if probability_report.get(key) != recalculated.get(key):
            raise ValueError(f"R100_CALIBRATION_{key.upper()}_MISMATCH")
    for key in ("brier_score", "log_loss", "max_reliability_gap"):
        if not _same_number(probability_report.get(key), recalculated.get(key)):
            raise ValueError(f"R100_CALIBRATION_{key.upper()}_MISMATCH")
    if probability_report.get("reliability_buckets") != recalculated.get("reliability_buckets"):
        if len(probability_report.get("reliability_buckets", [])) != len(recalculated["reliability_buckets"]):
            raise ValueError("R100_CALIBRATION_BUCKET_COUNT_MISMATCH")
        for actual, expected in zip(probability_report["reliability_buckets"], recalculated["reliability_buckets"]):
            for key in ("count", "lower", "upper"):
                if actual.get(key) != expected.get(key):
                    raise ValueError("R100_CALIBRATION_BUCKET_BOUNDARY_MISMATCH")
            for key in ("mean_probability", "realized_rate"):
                if not _same_number(actual.get(key), expected.get(key)):
                    raise ValueError("R100_CALIBRATION_BUCKET_METRIC_MISMATCH")

    last_completed = str(state.get("last_run_completed_at_utc") or "")
    generated = generated_at or last_completed
    if not generated:
        raise ValueError("R100_EVIDENCE_GENERATION_TIMESTAMP_MISSING")
    generated_dt = _parse_utc(generated)
    now = datetime.datetime.now(datetime.timezone.utc)
    if generated_dt > now:
        raise ValueError("R100_EVIDENCE_GENERATION_TIMESTAMP_IN_FUTURE")
    if _parse_utc(str(manifest["started_at_utc"])) > oos_start or campaign_end < oos_start:
        raise ValueError("R100_CAMPAIGN_WINDOW_INVALID")
    ended_at = str(manifest["campaign_end_at_utc"])
    _parse_utc(ended_at)
    if generated_dt < campaign_end:
        raise ValueError("R100_EVIDENCE_GENERATED_BEFORE_CAMPAIGN_END")

    combined_artifact_hash = _sha256_bytes(state_bytes + b"\0" + report_bytes)
    oos_window = f"{manifest['oos_start_at_utc']}/{manifest['campaign_end_at_utc']}"
    invariants = [
        "sealed_manifest_true",
        "campaign_complete_true",
        "no_pending_signals",
        "source_commit_pinned",
        "config_hash_pinned",
        "archive_hash_recomputed",
        "oos_samples_recounted",
        "oos_tick_coverage_recomputed",
        "oos_collection_gaps_bounded",
        "oos_expectancy_recomputed_positive",
        "multiple_testing_accounted",
        "calibration_metrics_recomputed",
        "retuning_after_seal_false",
        "execution_authorization_false",
        "capital_authority_false",
        "zero_order_submissions",
        "live_execution_blocked",
    ]
    base = {
        "source_commit": source_commit,
        "config_hash": config_hash,
        "archive_hash": archive_hash,
        "artifact_hash": combined_artifact_hash,
        "started_at": str(manifest["oos_start_at_utc"]),
        "ended_at": ended_at,
        "generated_at": generated,
    }
    records = {}
    records["prospective_oos.json"] = _build_record(
        evidence_id=f"r100-prospective-oos:{manifest['experiment_id']}",
        issuer="assurance.r100_evidence_adapter",
        domain_fields={
            "campaign_producer": producer,
            "censored_signal_count": len(censored),
            "sealed_prospective_data": True,
            "retuning_after_seal": False,
            "multiple_testing_accounted": True,
            "archive_hash": archive_hash,
            "strategy_version": str(manifest["strategy_version"]),
            "oos_window": oos_window,
            "min_trades_per_strategy_symbol_regime": len(oos_rows),
            "data_coverage_valid": True,
            "data_coverage_fraction": recomputed_coverage["data_coverage_fraction"],
            "max_observation_gap_seconds": recomputed_coverage["max_observation_gap_seconds"],
            "collection_window_count": recomputed_coverage["collection_window_count"],
            "capital_authority_granted": False,
            "orders_submitted": 0,
            "execution_authorized": False,
            "live_execution": False,
        },
        invariants=invariants,
        **base,
    )

    if recalculated["calibration_status"] == "VALIDATED_RESEARCH":
        qualifying_buckets = [
            bucket for bucket in recalculated["reliability_buckets"]
            if bucket["count"] >= 10
        ]
        records["calibration.json"] = _build_record(
            evidence_id=f"r100-calibration:{manifest['experiment_id']}",
            issuer="assurance.r100_evidence_adapter",
            domain_fields={
                "campaign_producer": producer,
                "calibration_validated": True,
                "drift_monitoring": True,
                "drift_detected": False,
                "sample_count": recalculated["sample_count"],
                "brier_score": recalculated["brier_score"],
                "log_loss": recalculated["log_loss"],
                "max_reliability_gap": recalculated["max_reliability_gap"],
                "reliability_buckets": qualifying_buckets,
                "capital_authority_granted": False,
                "orders_submitted": 0,
                "execution_authorized": False,
                "live_execution": False,
            },
            invariants=invariants,
            **base,
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".research_state/aurelia_r100_state.json")
    parser.add_argument("--report", default=".research_state/aurelia_r100_report.json")
    parser.add_argument("--out-dir", default="evidence")
    parser.add_argument("--status-out", default="artifacts/r100-evidence-adapter-status.json")
    args = parser.parse_args()

    status_path = pathlib.Path(args.status_out)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_paths = [out_dir / "prospective_oos.json", out_dir / "calibration.json"]
    for output_path in output_paths:
        output_path.unlink(missing_ok=True)

    try:
        state_path = pathlib.Path(args.state)
        report_path = pathlib.Path(args.report)
        state_bytes = state_path.read_bytes()
        report_bytes = report_path.read_bytes()
        state = json.loads(state_bytes)
        report = json.loads(report_bytes)
        records = adapt_sealed_campaign(
            state,
            report,
            state_bytes=state_bytes,
            report_bytes=report_bytes,
        )
        written = []
        for name, record in records.items():
            target = out_dir / name
            assurance.evidence_writer.write_evidence(target, record)
            written.append(str(target))
        calibration_written = str(out_dir / "calibration.json") in written
        oos_written = str(out_dir / "prospective_oos.json") in written
        result = {
            "schema": "aurelia.r100.evidence_adapter_status.v1",
            "status": (
                "PASS" if oos_written and calibration_written
                else "PARTIAL" if oos_written
                else "BLOCKED"
            ),
            "reason": (
                None if oos_written and calibration_written
                else "CALIBRATION_NOT_VALIDATED" if oos_written
                else "SEALED_OOS_EVIDENCE_NOT_WRITTEN"
            ),
            "source_commit": state["manifest"]["code_commit"],
            "archive_hash": report["archive_hash"],
            "written": written,
            "prospective_oos_evidence_written": oos_written,
            "calibration_evidence_written": calibration_written,
            "execution_economics_evidence_written": False,
            "capital_authority_granted": False,
            "orders_submitted": 0,
            "final_execution_authorization": False,
            "live_execution": "BLOCKED",
        }
        status_path.write_text(_canonical_json(result) + "\n", encoding="utf-8")
        print(_canonical_json(result))
        return 0
    except Exception as exc:
        result = {
            "schema": "aurelia.r100.evidence_adapter_status.v1",
            "status": "BLOCKED",
            "reason": f"{type(exc).__name__}:{exc}",
            "written": [],
            "execution_economics_evidence_written": False,
            "capital_authority_granted": False,
            "orders_submitted": 0,
            "final_execution_authorization": False,
            "live_execution": "BLOCKED",
        }
        status_path.write_text(_canonical_json(result) + "\n", encoding="utf-8")
        print(_canonical_json(result))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
