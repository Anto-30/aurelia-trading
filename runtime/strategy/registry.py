"""Canonical strategy qualification registry; research cannot self-promote."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

PASS = "PASS"
LIVE_QUALIFIED = "QUALIFIED_FOR_LIVE"
_REQUIRED_STATUS_FIELDS = (
    "implementation_status",
    "instrument_compatibility_status",
    "instrument_specification_status",
    "timeframe_status",
    "instrument_specification_status",
    "cost_profile_status",
    "out_of_sample_status",
    "walk_forward_status",
    "calibration_status",
    "net_economics_status",
    "robustness_status",
    "statistical_uncertainty_status",
    "forward_testing_status",
    "runtime_soak_status",
    "risk_governance_status",
)


def default_strategy_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "strategy_registry.json"


class StrategyQualificationRegistry:
    """Validated identity map with an intentionally conjunctive live gate."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        if document.get("schema") != "aurelia.strategy_registry.v1":
            raise ValueError("STRATEGY_REGISTRY_SCHEMA_INVALID")
        if document.get("capital_authority") is not False or document.get("execution_authority") is not False:
            raise ValueError("STRATEGY_REGISTRY_MUST_NOT_HAVE_CAPITAL_AUTHORITY")
        strategies = document.get("strategies")
        if not isinstance(strategies, list) or not strategies:
            raise ValueError("STRATEGY_REGISTRY_ENTRIES_REQUIRED")
        indexed: dict[str, dict[str, Any]] = {}
        for row in strategies:
            if not isinstance(row, dict):
                raise ValueError("STRATEGY_REGISTRY_ENTRY_INVALID")
            strategy_id = str(row.get("strategy_id") or "").strip()
            version = str(row.get("version") or "").strip()
            if not strategy_id or not version:
                raise ValueError("STRATEGY_ID_AND_VERSION_REQUIRED")
            if strategy_id in indexed:
                raise ValueError("STRATEGY_REGISTRY_DUPLICATE_ID:" + strategy_id)
            missing = [key for key in _REQUIRED_STATUS_FIELDS if not str(row.get(key) or "").strip()]
            if missing:
                raise ValueError("STRATEGY_REGISTRY_STATUS_FIELDS_MISSING:" + strategy_id + ":" + ",".join(missing))
            for field in ("verified_instrument_ids","instrument_categories","timeframes","qualification_evidence_ids"):
                if not isinstance(row.get(field), list):
                    raise ValueError("STRATEGY_REGISTRY_FIELD_MUST_BE_LIST:" + strategy_id + ":" + field)
            indexed[strategy_id] = dict(row)
        self.schema = str(document["schema"])
        self.registry_version = str(document.get("registry_version") or "")
        self.capital_authority = False
        self.execution_authority = False
        self._strategies = indexed

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "StrategyQualificationRegistry":
        target = Path(path) if path is not None else default_strategy_registry_path()
        try:
            document = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("STRATEGY_REGISTRY_UNREADABLE") from exc
        if not isinstance(document, dict):
            raise ValueError("STRATEGY_REGISTRY_ROOT_MUST_BE_OBJECT")
        return cls(document)

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> "StrategyQualificationRegistry":
        return cls(document)

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        row = self._strategies.get(strategy_id)
        return dict(row) if row is not None else None

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._strategies))

    def eligibility(self, strategy_id: str, version: str, instrument_id: str) -> dict[str, Any]:
        row = self._strategies.get(strategy_id)
        if row is None:
            return {"eligible": False, "status": "BLOCKED", "strategy_id": strategy_id,
                    "reasons": ["STRATEGY_NOT_REGISTERED"]}
        reasons: list[str] = []
        if str(version) != str(row.get("version")):
            reasons.append("STRATEGY_VERSION_MISMATCH")
        if row.get("qualification_status") != LIVE_QUALIFIED:
            reasons.append("STRATEGY_NOT_QUALIFIED_FOR_LIVE")
        if row.get("implementation_status") != "VERIFIED":
            reasons.append("STRATEGY_IMPLEMENTATION_NOT_VERIFIED")
        if row.get("instrument_compatibility_status") != PASS:
            reasons.append("STRATEGY_INSTRUMENT_COMPATIBILITY_NOT_VERIFIED")
        if row.get("instrument_specification_status") != PASS:
            reasons.append("INSTRUMENT_SPECIFICATION_NOT_VERIFIED")
        if instrument_id not in row.get("verified_instrument_ids", []):
            reasons.append("INSTRUMENT_NOT_VERIFIED_FOR_STRATEGY")
        if row.get("timeframe_status") != PASS:
            reasons.append("STRATEGY_TIMEFRAME_NOT_VERIFIED")
        for field in _REQUIRED_STATUS_FIELDS:
            expected = "VERIFIED" if field == "implementation_status" else PASS
            if row.get(field) != expected:
                reasons.append(field.upper() + "_NOT_PASS")
        if not row.get("qualification_evidence_ids") or any(not str(x).strip() for x in row.get("qualification_evidence_ids", [])):
            reasons.append("QUALIFICATION_EVIDENCE_IDS_MISSING")
        for field, reason in (
            ("reviewer","QUALIFICATION_REVIEWER_MISSING"),
            ("qualified_source_revision","QUALIFIED_SOURCE_REVISION_MISSING"),
            ("strategy_hash","STRATEGY_HASH_MISSING"),
            ("risk_profile","STRATEGY_RISK_PROFILE_MISSING"),
        ):
            if not str(row.get(field) or "").strip():
                reasons.append(reason)
        for field, reason in (
            ("instrument_categories","STRATEGY_INSTRUMENT_CATEGORIES_MISSING"),
            ("timeframes","STRATEGY_TIMEFRAMES_MISSING"),
            ("data_requirements","STRATEGY_DATA_REQUIREMENTS_MISSING"),
            ("execution_assumptions","STRATEGY_EXECUTION_ASSUMPTIONS_MISSING"),
        ):
            if not isinstance(row.get(field), list) or not row.get(field):
                reasons.append(reason)
        return {"eligible": not reasons, "status": "PASS" if not reasons else "BLOCKED",
                "strategy_id": strategy_id, "version": str(version), "instrument_id": instrument_id,
                "reasons": list(dict.fromkeys(reasons))}
