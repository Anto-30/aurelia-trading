from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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
    material = list(rows)
    archive = ProspectiveArchive(
        strategy_id=strategy_id,
        symbol=symbol,
        regime=regime,
        started_at_utc=started_at_utc,
        data_hash=_data_hash(material),
        sealed=True,
        row_count=len(material),
    )
    Path(output_path).write_text(
        json.dumps(
            {"archive": archive.__dict__, "rows": material},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return archive


def verify_sealed_archive(path: str | Path) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    archive = payload["archive"]
    rows = payload["rows"]
    if not archive["sealed"]:
        return False
    return archive["data_hash"] == _data_hash(rows)
