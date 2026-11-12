"""Legacy Deriv R_100 archive support is quarantined by ATOS v2.0 §4.

This module may verify the integrity of an existing historical archive, but it must
not create new durable R_100 archives. R_100 output is not eligible evidence for
EURUSD/XAUUSD FX or SMC research, Track A/Track B, or strategy promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


QUARANTINE_STATUS = "QUARANTINED"
QUARANTINE_REASON = (
    "DERIV_SYNTHETIC_R100_NOT_ELIGIBLE_FOR_FX_SMC_OR_STRATEGY_PROMOTION"
)


@dataclass(frozen=True)
class ProspectiveArchive:
    strategy_id: str
    symbol: str
    regime: str
    started_at_utc: str
    data_hash: str
    sealed: bool
    row_count: int


def _data_hash(rows: Iterable[dict]) -> str:
    canonical = json.dumps(
        list(rows), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seal_r100_archive(
    rows: Iterable[dict],
    *,
    strategy_id: str,
    symbol: str,
    regime: str,
    started_at_utc: str,
    output_path: str | Path,
) -> ProspectiveArchive:
    """Refuse new durable R_100 archives; historical integrity checks remain read-only."""
    del rows, strategy_id, symbol, regime, started_at_utc, output_path
    raise RuntimeError(
        "R100_ARCHIVE_QUARANTINED: new durable Deriv synthetic-index archives are disabled "
        "by ATOS v2.0 §4; this data is not FX/SMC evidence"
    )


def verify_sealed_archive(path: str | Path) -> bool:
    """Verify historical archive integrity only; True does not imply research eligibility."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    archive = payload["archive"]
    rows = payload["rows"]
    if not archive["sealed"]:
        return False
    return archive["data_hash"] == _data_hash(rows)
