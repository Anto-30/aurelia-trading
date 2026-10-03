from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class LiveReleaseState:
    live_trading_enabled: bool
    final_execution_authorization: bool
    capital_plane_mode: str

    @property
    def may_move_capital(self) -> bool:
        return self.live_trading_enabled and self.final_execution_authorization and self.capital_plane_mode == "LIVE"

def _yaml_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1"}

def read_live_release(path: Path) -> LiveReleaseState:
    values: dict[str, str] = {}
    if not path.exists():
        return LiveReleaseState(False, False, "UNKNOWN")
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key,value=line.split(":",1)
        values[key.strip()]=value.strip()
    return LiveReleaseState(
        live_trading_enabled=_yaml_bool(values.get("live_trading_enabled","false")),
        final_execution_authorization=_yaml_bool(values.get("FINAL_EXECUTION_AUTHORIZATION","false")),
        capital_plane_mode=values.get("capital_plane_mode","UNKNOWN"),
    )
