"""Strict Jev decision contract. No model output can skip deterministic validation."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

REGIMES = frozenset({"trending", "mean_reverting", "high_vol", "crisis"})
DIRECTIONS = frozenset({"long", "short", "neutral"})
RISK_STATES = frozenset({"safe", "near_limit", "reduce"})
EXPECTED_FIELDS = frozenset({
    "regime", "direction", "setup_quality", "risk_state", "confidence",
    "position_size_pct", "stop_loss_ticks", "take_profit_ticks",
})


class DecisionSchemaError(ValueError):
    """Raised when a BRAIN/strategy candidate violates the closed Jev schema."""


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionSchemaError(f"{field.upper()}_MUST_BE_NUMERIC")
    parsed = float(value)
    if not isfinite(parsed):
        raise DecisionSchemaError(f"{field.upper()}_MUST_BE_FINITE")
    return parsed


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DecisionSchemaError(f"{field.upper()}_MUST_BE_INTEGER")
    return value


@dataclass(frozen=True)
class JevDecision:
    regime: str
    direction: str
    setup_quality: int
    risk_state: str
    confidence: float
    position_size_pct: float
    stop_loss_ticks: int
    take_profit_ticks: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "JevDecision":
        if not isinstance(payload, Mapping):
            raise DecisionSchemaError("DECISION_MUST_BE_OBJECT")
        keys = frozenset(payload.keys())
        if keys != EXPECTED_FIELDS:
            missing = sorted(EXPECTED_FIELDS - keys)
            extra = sorted(keys - EXPECTED_FIELDS)
            raise DecisionSchemaError(
                "DECISION_FIELDS_MISMATCH"
                + (":MISSING=" + ",".join(missing) if missing else "")
                + (":EXTRA=" + ",".join(extra) if extra else "")
            )

        regime = payload["regime"]
        direction = payload["direction"]
        risk_state = payload["risk_state"]
        if not isinstance(regime, str) or regime not in REGIMES:
            raise DecisionSchemaError("REGIME_INVALID")
        if not isinstance(direction, str) or direction not in DIRECTIONS:
            raise DecisionSchemaError("DIRECTION_INVALID")
        if not isinstance(risk_state, str) or risk_state not in RISK_STATES:
            raise DecisionSchemaError("RISK_STATE_INVALID")

        quality = _integer(payload["setup_quality"], "setup_quality")
        confidence = _number(payload["confidence"], "confidence")
        size = _number(payload["position_size_pct"], "position_size_pct")
        stop = _integer(payload["stop_loss_ticks"], "stop_loss_ticks")
        target = _integer(payload["take_profit_ticks"], "take_profit_ticks")

        if not 0 <= quality <= 3:
            raise DecisionSchemaError("SETUP_QUALITY_OUT_OF_RANGE")
        if not 0.0 <= confidence <= 1.0:
            raise DecisionSchemaError("CONFIDENCE_OUT_OF_RANGE")
        if not 0.0 <= size <= 2.0:
            raise DecisionSchemaError("POSITION_SIZE_OUT_OF_RANGE")
        if stop < 1 or target < 1:
            raise DecisionSchemaError("STOP_AND_TARGET_MUST_BE_POSITIVE_TICKS")
        if direction == "neutral" and size != 0.0:
            raise DecisionSchemaError("NEUTRAL_DIRECTION_REQUIRES_ZERO_SIZE")
        if direction in {"long", "short"} and size <= 0.0:
            raise DecisionSchemaError("DIRECTIONAL_SIGNAL_REQUIRES_POSITIVE_SIZE")

        return cls(
            regime=regime, direction=direction, setup_quality=quality,
            risk_state=risk_state, confidence=confidence, position_size_pct=size,
            stop_loss_ticks=stop, take_profit_ticks=target,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime, "direction": self.direction,
            "setup_quality": self.setup_quality, "risk_state": self.risk_state,
            "confidence": self.confidence, "position_size_pct": self.position_size_pct,
            "stop_loss_ticks": self.stop_loss_ticks, "take_profit_ticks": self.take_profit_ticks,
        }
