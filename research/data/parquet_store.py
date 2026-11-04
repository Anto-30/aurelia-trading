from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .deriv_tick_ingestor import IngestionResult, Tick


@dataclass(frozen=True)
class StoreWriteResult:
    parquet_paths: tuple[str, ...]
    provenance_paths: tuple[str, ...]


class ParquetTickStore:
    """Append-only Parquet fragments partitioned by symbol and UTC date."""

    _SYMBOL = re.compile(r"^[A-Z0-9_]{2,30}$")
    _RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

    def __init__(self, root: str | Path = "data/ticks") -> None:
        self.root = Path(root)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        encoded = json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
        temporary.write_text(encoded, encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)

    def write_page(
        self,
        *,
        symbol: str,
        run_id: str,
        page_number: int,
        ticks: Sequence[Tick],
        request: dict,
        source_sha: str,
        page_sha256: str,
    ) -> StoreWriteResult:
        if not isinstance(symbol, str) or not self._SYMBOL.fullmatch(symbol):
            raise ValueError("PARQUET_SYMBOL_INVALID")
        if not isinstance(run_id, str) or not self._RUN_ID.fullmatch(run_id):
            raise ValueError("PARQUET_RUN_ID_INVALID")
        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise ValueError("PARQUET_PAGE_NUMBER_INVALID")
        if not ticks:
            raise ValueError("PARQUET_EMPTY_PAGE")
        for tick in ticks:
            if tick.symbol != symbol or tick.validate() is not True:
                raise ValueError("PARQUET_TICK_RECORD_INVALID")
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("PYARROW_DEPENDENCY_MISSING") from exc

        grouped: dict[str, list[Tick]] = {}
        for tick in ticks:
            day = datetime.fromtimestamp(tick.epoch, tz=timezone.utc).date().isoformat()
            grouped.setdefault(day, []).append(tick)

        parquet_paths: list[str] = []
        provenance_paths: list[str] = []
        for day, rows in sorted(grouped.items()):
            partition = self.root / symbol / day
            partition.mkdir(parents=True, exist_ok=True)
            stem = f"part-{run_id}-p{page_number:06d}"
            parquet_path = partition / f"{stem}.parquet"
            provenance_path = partition / f"{stem}.provenance.json"
            if parquet_path.exists() or provenance_path.exists():
                raise FileExistsError("PARQUET_PAGE_ALREADY_EXISTS")

            table = pa.table({
                "symbol": pa.array([item.symbol for item in rows], type=pa.string()),
                "epoch": pa.array([item.epoch for item in rows], type=pa.int64()),
                "quote": pa.array([float(item.quote) for item in rows], type=pa.float64()),
            })
            temporary = parquet_path.with_name(parquet_path.name + ".tmp")
            pq.write_table(table, temporary, compression="zstd", version="2.6")
            os.chmod(temporary, 0o600)
            temporary.replace(parquet_path)
            parquet_hash = self._sha256(parquet_path)
            provenance = {
                "schema": "aurelia.deriv_tick_page.v1",
                "symbol": symbol,
                "partition_date_utc": day,
                "run_id": run_id,
                "page_number": page_number,
                "tick_count": len(rows),
                "first_epoch": min(item.epoch for item in rows),
                "last_epoch": max(item.epoch for item in rows),
                "request": request,
                "source_sha": source_sha,
                "deriv_page_payload_sha256": page_sha256,
                "parquet_sha256": parquet_hash,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "endpoint": "wss://api.derivws.com/trading/v1/options/ws/public",
                "authorization": "NONE_PUBLIC_MARKET_DATA",
                "capital_authority": False,
                "orders_submitted": 0,
                "true_volume_present": False,
            }
            self._write_json_atomic(provenance_path, provenance)
            parquet_paths.append(str(parquet_path))
            provenance_paths.append(str(provenance_path))

        return StoreWriteResult(tuple(parquet_paths), tuple(provenance_paths))

    def write_run_manifest(self, result: IngestionResult, *, source_sha: str) -> str:
        if not self._SYMBOL.fullmatch(result.symbol) or not self._RUN_ID.fullmatch(result.run_id):
            raise ValueError("PARQUET_RUN_MANIFEST_ID_INVALID")
        path = self.root / result.symbol / f"{result.run_id}.manifest.json"
        payload = {
            "schema": "aurelia.deriv_tick_ingestion_run.v1",
            "status": result.status,
            "symbol": result.symbol,
            "start_epoch": result.start_epoch,
            "end_epoch": result.end_epoch,
            "pages_fetched": result.pages_fetched,
            "tick_count": result.tick_count,
            "duplicates_removed": result.duplicates_removed,
            "max_gap_seconds": result.max_gap_seconds,
            "gaps_over_threshold": result.gaps_over_threshold,
            "first_epoch": result.first_epoch,
            "last_epoch": result.last_epoch,
            "dataset_sha256": result.dataset_sha256,
            "parquet_paths": list(result.parquet_paths),
            "provenance_paths": list(result.provenance_paths),
            "source_sha": source_sha,
            "capital_authority": False,
            "orders_submitted": 0,
            "true_volume_present": False,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._write_json_atomic(path, payload)
        return str(path)

    def read_ticks(self, symbol: str) -> list[Tick]:
        if not isinstance(symbol, str) or not self._SYMBOL.fullmatch(symbol):
            raise ValueError("PARQUET_SYMBOL_INVALID")
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("PYARROW_DEPENDENCY_MISSING") from exc
        directory = self.root / symbol
        rows: list[Tick] = []
        if not directory.exists():
            return rows
        for path in sorted(directory.rglob("*.parquet")):
            table = pq.read_table(path, columns=["symbol", "epoch", "quote"])
            for row in table.to_pylist():
                rows.append(Tick(row["symbol"], row["epoch"], row["quote"]))
        rows.sort(key=lambda item: item.epoch)
        return rows
