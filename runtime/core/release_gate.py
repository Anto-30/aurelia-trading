from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_REQUIRED_LOCK_KEYS = frozenset({
    "schema",
    "live_trading_enabled",
    "FINAL_EXECUTION_AUTHORIZATION",
    "LIVE_EXECUTION",
    "capital_plane_mode",
    "research_capital_authority",
    "external_repositories_capital_forbidden",
    "blind_resubmission",
    "kill_switch_independent",
})


@dataclass(frozen=True)
class LiveReleaseState:
    live_trading_enabled: bool
    final_execution_authorization: bool
    capital_plane_mode: str
    live_execution_enabled: bool = False
    schema_valid: bool = False
    configuration_unambiguous: bool = False
    research_capital_authority_disabled: bool = False
    external_repositories_capital_forbidden: bool = False
    blind_resubmission_disabled: bool = False
    kill_switch_independent: bool = False

    @property
    def may_move_capital(self) -> bool:
        """Fail closed unless all execution and independent safety invariants agree."""
        return all((
            self.schema_valid,
            self.configuration_unambiguous,
            self.live_trading_enabled,
            self.final_execution_authorization,
            self.capital_plane_mode.strip().upper() == "LIVE",
            self.live_execution_enabled,
            self.research_capital_authority_disabled,
            self.external_repositories_capital_forbidden,
            self.blind_resubmission_disabled,
            self.kill_switch_independent,
        ))


def _strict_true(value: str) -> bool:
    return value.strip().lower() == "true"


def _strict_false(value: str) -> bool:
    return value.strip().lower() == "false"


def read_live_release(path: Path) -> LiveReleaseState:
    if not path.exists():
        return LiveReleaseState(False, False, "UNKNOWN")

    values: dict[str, str] = {}
    duplicate_keys: set[str] = set()
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if not key:
                return LiveReleaseState(False, False, "UNKNOWN")
            if key in values:
                duplicate_keys.add(key)
            values[key] = value.strip()
    except (OSError, UnicodeError):
        return LiveReleaseState(False, False, "UNKNOWN")

    unambiguous = not duplicate_keys and _REQUIRED_LOCK_KEYS.issubset(values.keys())
    schema_valid = values.get("schema", "").strip() == "aurelia.live_lock.v1"
    return LiveReleaseState(
        live_trading_enabled=_strict_true(values.get("live_trading_enabled", "")),
        final_execution_authorization=_strict_true(
            values.get("FINAL_EXECUTION_AUTHORIZATION", "")
        ),
        capital_plane_mode=values.get("capital_plane_mode", "UNKNOWN").strip().upper(),
        live_execution_enabled=(
            values.get("LIVE_EXECUTION", "").strip().upper() == "ENABLED"
        ),
        schema_valid=schema_valid,
        configuration_unambiguous=unambiguous,
        research_capital_authority_disabled=_strict_false(
            values.get("research_capital_authority", "")
        ),
        external_repositories_capital_forbidden=_strict_true(
            values.get("external_repositories_capital_forbidden", "")
        ),
        blind_resubmission_disabled=_strict_false(
            values.get("blind_resubmission", "")
        ),
        kill_switch_independent=_strict_true(
            values.get("kill_switch_independent", "")
        ),
    )
