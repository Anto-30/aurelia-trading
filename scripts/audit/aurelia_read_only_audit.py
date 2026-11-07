"""Read-only, fail-closed AURELIA governance audit.

Run from the repository root:
    python -m scripts.audit.aurelia_read_only_audit

This audit performs no broker authentication, order submission, process control,
configuration writes, deployment, or network requests. Every FAIL or UNKNOWN
result produces a non-zero exit code.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIVE_LOCK_PATH = Path("config/LIVE_LOCK.yaml")
AUTHORITY_PATH = Path("runtime/core/authority.py")
SOURCE_OF_TRUTH_PATH = Path("AURELIA_SOURCE_OF_TRUTH.json")
DATA_PATH = Path(os.environ.get("AURELIA_R100_M15_PARQUET", "data/R_100_M15.parquet"))
EXPECTED_LIVE_LOCK_SHA256 = "72a8e51129a4dd6f7bac1ccb5b181c7b0c8b0d1fc16933ca61ffe349a0c1d6b7"
MAX_DATA_AGE = timedelta(hours=24)
MAX_M15_GAP_SECONDS = 900
WORKER_MARKER = os.environ.get("AURELIA_WORKER_MARKER", "runtime/main.py")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
LOG = logging.getLogger("aurelia.read_only_audit")


@dataclass
class Audit:
    results: dict[str, dict[str, str]] = field(default_factory=dict)

    def record(self, name: str, status: str, message: str) -> None:
        normalized = status.upper()
        if normalized not in {"PASS", "FAIL", "UNKNOWN"}:
            normalized = "UNKNOWN"
        self.results[name] = {"status": normalized, "message": message}
        getattr(LOG, "info" if normalized == "PASS" else "error")(
            "[%s] %s", name, message
        )

    @property
    def exit_code(self) -> int:
        return 0 if self.results and all(
            result["status"] == "PASS" for result in self.results.values()
        ) else 1

    def summary(self) -> dict[str, Any]:
        return {
            "schema": "aurelia.read_only_audit.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "capital_authority": False,
            "order_submission_permitted": False,
            "results": self.results,
            "exit_code": self.exit_code,
        }


def _parse_flat_yaml(text: str) -> dict[str, str]:
    """Parse the scalar key/value subset used by canonical LIVE_LOCK.yaml."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def check_live_lock(root: Path) -> dict[str, str]:
    path = root / LIVE_LOCK_PATH
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {"status": "FAIL", "message": f"Canonical LIVE_LOCK unavailable: {exc}"}
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_LIVE_LOCK_SHA256:
        return {
            "status": "FAIL",
            "message": f"LIVE_LOCK SHA-256 mismatch: {digest}",
        }
    values = _parse_flat_yaml(raw.decode("utf-8"))
    expected = {
        "schema": "aurelia.live_lock.v1",
        "live_trading_enabled": "false",
        "FINAL_EXECUTION_AUTHORIZATION": "false",
        "LIVE_EXECUTION": "BLOCKED",
        "capital_plane_mode": "VERIFY_ONLY",
        "research_capital_authority": "false",
        "external_repositories_capital_forbidden": "true",
        "blind_resubmission": "false",
        "kill_switch_independent": "true",
    }
    if values != expected:
        return {
            "status": "FAIL",
            "message": "LIVE_LOCK content does not match the complete approved invariant set",
        }
    return {"status": "PASS", "message": f"Canonical LIVE_LOCK SHA-256 verified: {digest}"}


def check_probability_policy(root: Path) -> dict[str, str]:
    authority = root / AUTHORITY_PATH
    source = root / SOURCE_OF_TRUTH_PATH
    try:
        code = authority.read_text(encoding="utf-8")
        source_data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "message": f"Probability policy source unavailable/invalid: {exc}"}

    min_match = re.search(r"^MIN_PROBABILITY\s*=\s*(0?\.\d+|\d+(?:\.\d+)?)\s*$", code, re.M)
    max_match = re.search(r"^MAX_PROBABILITY\s*=\s*(0?\.\d+|\d+(?:\.\d+)?)\s*$", code, re.M)
    if not min_match or not max_match:
        return {"status": "FAIL", "message": "Canonical probability constants could not be parsed"}
    try:
        minimum, maximum = float(min_match.group(1)), float(max_match.group(1))
        source_min = float(source_data["probability_min"])
        source_max = float(source_data["probability_max"])
    except (KeyError, TypeError, ValueError):
        return {"status": "FAIL", "message": "Probability policy fields are missing or invalid"}

    if (minimum, maximum) != (0.50, 0.75) or (source_min, source_max) != (minimum, maximum):
        return {
            "status": "FAIL",
            "message": (
                "Probability policy mismatch: authority="
                f"[{minimum}, {maximum}], source_of_truth=[{source_min}, {source_max}]"
            ),
        }
    return {
        "status": "PASS",
        "message": "Probability policy reconciled: inclusive [0.50, 0.75], no clipping",
    }


def check_git_integrity(root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root, capture_output=True, text=True, check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "FAIL", "message": f"Git integrity check unavailable: {exc}"}
    if result.stdout.strip():
        return {"status": "FAIL", "message": "Working tree has modified or untracked files"}
    return {"status": "PASS", "message": "Entire working tree is clean"}


def check_worker_heartbeat(marker: str = WORKER_MARKER) -> dict[str, str]:
    proc = Path("/proc")
    if not proc.is_dir():
        return {"status": "UNKNOWN", "message": "Linux /proc process inventory unavailable"}
    current_pid = os.getpid()
    matches: list[str] = []
    try:
        for entry in proc.iterdir():
            if not entry.name.isdigit() or int(entry.name) == current_pid:
                continue
            try:
                cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                    "utf-8", errors="replace"
                )
            except OSError:
                continue
            if marker in cmdline:
                matches.append(entry.name)
    except OSError as exc:
        return {"status": "UNKNOWN", "message": f"Process inventory failed: {exc}"}
    if not matches:
        return {"status": "FAIL", "message": f"No process matched configured worker marker {marker!r}"}
    return {"status": "PASS", "message": f"Worker process marker found; PID(s): {', '.join(matches)}"}


def check_data_readiness(root: Path, data_path: Path = DATA_PATH) -> dict[str, str]:
    path = data_path if data_path.is_absolute() else root / data_path
    if not path.is_file():
        return {"status": "FAIL", "message": f"Required dataset missing: {path}"}
    try:
        import pandas as pd  # Optional dependency; absence is a hard readiness failure.
        frame = pd.read_parquet(path)
    except Exception as exc:
        return {"status": "FAIL", "message": f"Parquet read/decoder validation failed: {exc}"}
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        return {"status": "FAIL", "message": "Dataset must be non-empty with a DatetimeIndex"}
    if frame.index.tz is None:
        return {"status": "FAIL", "message": "Dataset timestamps must be timezone-aware"}
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        return {"status": "FAIL", "message": "Dataset timestamps are unordered or duplicated"}
    required = {"open", "high", "low", "close"}
    if not required.issubset({str(column).lower() for column in frame.columns}):
        return {"status": "FAIL", "message": "Dataset is missing one or more OHLC columns"}
    utc_index = frame.index.tz_convert("UTC")
    now = pd.Timestamp.now(tz="UTC")
    age = now - utc_index[-1]
    if age < pd.Timedelta(0) or age > pd.Timedelta(MAX_DATA_AGE):
        return {"status": "FAIL", "message": f"Dataset latest timestamp age invalid/stale: {age}"}
    gaps = utc_index.to_series().diff().dropna().dt.total_seconds()
    if not gaps.empty and float(gaps.max()) > MAX_M15_GAP_SECONDS:
        return {"status": "FAIL", "message": f"Dataset gap exceeds 900 seconds: {float(gaps.max())}"}
    return {"status": "PASS", "message": f"R_100 M15 dataset structurally valid; latest UTC bar: {utc_index[-1].isoformat()}"}


def run_audit(root: Path = ROOT) -> int:
    audit = Audit()
    checks = {
        "Git_Integrity": check_git_integrity(root),
        "Probability_Policy": check_probability_policy(root),
        "LIVE_LOCK": check_live_lock(root),
        "Worker_Heartbeat": check_worker_heartbeat(),
        "Data_Readiness": check_data_readiness(root),
    }
    for name, result in checks.items():
        audit.record(name, result["status"], result["message"])

    # Deliberately no legacy Binary WS v3 request: AURELIA documents that endpoint
    # as diagnostic-only. This audit does not authenticate or call broker endpoints.
    audit.record(
        "Deriv_Connectivity",
        "UNKNOWN",
        "Not probed: legacy ws.binaryws.com is not an approved production path; "
        "use the separately governed modern Deriv verifier when explicitly authorized.",
    )
    payload = audit.summary()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return audit.exit_code


if __name__ == "__main__":
    raise SystemExit(run_audit())
