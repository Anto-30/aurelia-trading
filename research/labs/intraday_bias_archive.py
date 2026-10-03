from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class ArchiveReceipt:
    path: str
    row_count: int
    content_hash: str
    previous_hash: str | None
    sealed: bool

def _canonical(rows: Iterable[dict]) -> str:
    return json.dumps(list(rows), sort_keys=True, separators=(",", ":"), allow_nan=False)

def append_observations(path: str | Path, rows: Iterable[dict]) -> ArchiveReceipt:
    target = Path(path)
    material = list(rows)
    if target.exists():
        payload = json.loads(target.read_text(encoding="utf-8"))
        if payload.get("sealed"):
            raise ValueError("sealed archive is immutable")
        previous_hash, existing = payload.get("content_hash"), payload.get("rows", [])
    else:
        previous_hash, existing = None, []
    combined = existing + material
    content_hash = hashlib.sha256(_canonical(combined).encode("utf-8")).hexdigest()
    receipt = ArchiveReceipt(str(target), len(combined), content_hash, previous_hash, False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({**asdict(receipt), "rows": combined},
                                 sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return receipt

def seal_archive(path: str | Path) -> ArchiveReceipt:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("sealed"):
        return ArchiveReceipt(str(target), len(payload.get("rows", [])), payload["content_hash"],
                              payload.get("previous_hash"), True)
    payload["sealed"] = True
    target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return ArchiveReceipt(str(target), len(payload.get("rows", [])), payload["content_hash"],
                          payload.get("previous_hash"), True)

def verify_archive(path: str | Path) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = hashlib.sha256(_canonical(payload.get("rows", [])).encode("utf-8")).hexdigest()
    return expected == payload.get("content_hash") and isinstance(payload.get("rows"), list)
