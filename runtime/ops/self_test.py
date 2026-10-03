from __future__ import annotations

from pathlib import Path

from runtime.core.capabilities import Capability, RESEARCH_CAPABILITIES
from runtime.core.release_gate import read_live_release
from runtime.core.runtime_config import load_config_hash


def run_self_test(root: Path) -> dict[str, object]:
    release = read_live_release(root / "config" / "LIVE_LOCK.yaml")
    return {
        "runtime_config_hash": load_config_hash(root),
        "live_lock_present": (root / "config" / "LIVE_LOCK.yaml").exists(),
        "runtime_main_present": (root / "runtime" / "main.py").exists(),
        "deriv_adapter_present": (root / "runtime" / "adapters" / "deriv_adapter.py").exists(),
        "capital_executor_present": (root / "runtime" / "broker" / "executor.py").exists(),
        "research_can_submit": RESEARCH_CAPABILITIES.allows(Capability.SUBMIT_ORDER),
        "live_release_may_move_capital": release.may_move_capital,
        "final_execution_authorization": release.final_execution_authorization,
        "live_trading_enabled": release.live_trading_enabled,
        "status": "PASS" if not release.may_move_capital and not RESEARCH_CAPABILITIES.allows(Capability.SUBMIT_ORDER) else "BLOCKED",
    }
