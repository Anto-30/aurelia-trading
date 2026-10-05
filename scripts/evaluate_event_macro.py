#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from research.event_driven_macro import (
    EventDrivenMacroEngine,
    MacroPolicy,
    MarketSnapshot,
    PoliticalSnapshot,
    ResultStatus,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "event_driven_macro_policy.json"


def _dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed


def _status(value: str | None) -> ResultStatus:
    return ResultStatus(str(value or "UNKNOWN").upper())


def _political(payload: Mapping[str, Any]) -> PoliticalSnapshot:
    return PoliticalSnapshot(
        house_dem_probability=float(payload["house_dem_probability"]),
        senate_dem_probability=float(payload["senate_dem_probability"]),
        house_status=_status(payload.get("house_status")),
        senate_status=_status(payload.get("senate_status")),
        contested=bool(payload.get("contested", False)),
        as_of_utc=_dt(payload.get("as_of_utc")),
        source_ids=tuple(str(v) for v in payload.get("source_ids", [])),
    )


def _market(payload: Mapping[str, Any]) -> MarketSnapshot:
    names = (
        "spx_return_pct",
        "nasdaq_return_pct",
        "small_cap_return_pct",
        "two_year_yield_change_bps",
        "ten_year_yield_change_bps",
        "usd_return_pct",
        "gold_return_pct",
        "oil_return_pct",
        "credit_spread_change_bps",
        "vix_level",
        "vix_change_pct",
        "crypto_return_pct",
    )
    values = {
        name: None if payload.get(name) is None else float(payload[name])
        for name in names
    }
    values["as_of_utc"] = _dt(payload.get("as_of_utc"))
    return MarketSnapshot(**values)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        try:
            return value.value
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(v) for v in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate AURELIA event-driven macro posture (research-only)."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("INPUT_MUST_BE_OBJECT")

    policy_payload = json.loads(args.policy.read_text(encoding="utf-8"))
    if not isinstance(policy_payload, dict):
        raise ValueError("POLICY_MUST_BE_OBJECT")

    decision = EventDrivenMacroEngine(
        MacroPolicy.from_mapping(policy_payload)
    ).evaluate(
        previous=_political(payload["previous"]),
        current=_political(payload["current"]),
        market=_market(payload["market"]),
        now=_dt(payload.get("now_utc")),
        event_type=str(payload.get("event_type", "ELECTION_RESULT")),
    )

    output = {
        "schema": "aurelia.event_driven_macro_decision.v1",
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_lock_mutation": False,
        "decision": asdict(decision),
    }
    print(json.dumps(_json_ready(output), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
