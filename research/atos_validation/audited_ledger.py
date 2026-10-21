"""Append-only, hash-chained simulator audit ledger for AURELIA research.

This module does not generate strategy signals or simulate fills. The frozen strategy
simulator must call record_decision for every candidate decision and record_trade only
when a trade is actually closed, using its real prices/costs. All records are bound to
the supplied historical-data and model/config SHA-256 digests. No order API exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "aurelia.audited_trade_ledger.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIONS = {"ENTER_LONG", "ENTER_SHORT", "NO_TRADE"}


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite_number(value: Any, name: str, *, minimum: float | None = None, strict: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a numeric value")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if strict and minimum is not None and result <= minimum:
        raise ValueError(f"{name} must be greater than {minimum}")
    if not strict and minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def _aware_utc(value: str | datetime, name: str) -> datetime:
    if isinstance(value, str):
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValueError(f"{name} must be an ISO-8601 string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_iso(epoch: int) -> str:
    return _iso(datetime.fromtimestamp(epoch, timezone.utc))


def _validate_digest(value: str, name: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")
    return value


class AuditedLedgerWriter:
    """Create a new immutable-on-completion JSONL ledger; existing paths are refused."""

    def __init__(
        self,
        path: str | Path,
        *,
        symbol: str,
        data_sha256: str,
        granularity_seconds: int = 60,
        strategy_code_sha256: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"refusing to overwrite existing audit ledger: {self.path}")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be non-empty")
        if granularity_seconds not in (60, 900):
            raise ValueError("granularity_seconds must be 60 or 900")
        self.symbol = symbol.strip()
        self.data_sha256 = _validate_digest(data_sha256, "data_sha256")
        self.strategy_code_sha256 = (
            _validate_digest(strategy_code_sha256, "strategy_code_sha256")
            if strategy_code_sha256 is not None else None
        )
        self.granularity_seconds = granularity_seconds
        self._head_hash: str | None = None
        self._strategies: set[str] = set()
        self._fold_ids: set[str] = set()
        self._config_hashes: set[str] = set()
        self._accepted_decisions: dict[str, dict[str, Any]] = {}
        self._decision_count = 0
        self._trade_count = 0
        self._cancel_count = 0
        self._stream = self.path.open("x", encoding="utf-8", newline="\n")
        self._closed = False
        self._created_at_utc = datetime.now(timezone.utc)

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("ledger is already closed")
        record["previous_record_sha256"] = self._head_hash
        record["record_sha256"] = _sha256(_canonical(record))
        line = json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        self._stream.write(line + "\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._head_hash = record["record_sha256"]
        return record

    def record_decision(
        self,
        *,
        signal_bar_epoch: int,
        strategy: str,
        model_config_sha256: str,
        fold_id: str,
        action: str,
        reason_codes: Iterable[str],
        hmm_regime_state: str | int | None,
        accepted: bool,
        probability: float | None = None,
    ) -> str:
        """Record every signal decision, including no-trade/rejected decisions.

        signal_bar_epoch is the just-closed candle N-1; its execution candle is N.
        This strict adjacency guard prevents using the current candle close before it
        was known.
        """
        if not isinstance(strategy, str) or not strategy.strip():
            raise ValueError("strategy must be non-empty")
        if not isinstance(fold_id, str) or not fold_id.strip():
            raise ValueError("fold_id must be non-empty")
        config_hash = _validate_digest(model_config_sha256, "model_config_sha256")
        if isinstance(signal_bar_epoch, bool) or not isinstance(signal_bar_epoch, int) or signal_bar_epoch < 0:
            raise ValueError("signal_bar_epoch must be a nonnegative integer epoch")
        if signal_bar_epoch % self.granularity_seconds:
            raise ValueError("signal_bar_epoch must align to the candle boundary")
        if action not in ACTIONS:
            raise ValueError(f"action must be one of {sorted(ACTIONS)}")
        if not isinstance(accepted, bool):
            raise ValueError("accepted must be boolean")
        reasons = list(reason_codes)
        if any(not isinstance(item, str) or not item.strip() for item in reasons):
            raise ValueError("reason_codes must contain non-empty strings")
        if action == "NO_TRADE" and accepted:
            raise ValueError("NO_TRADE cannot be accepted as an entry")
        if action in {"ENTER_LONG", "ENTER_SHORT"} and accepted and hmm_regime_state is None:
            raise ValueError("accepted entries require a recorded HMM regime state")
        if probability is not None:
            probability = _finite_number(probability, "probability", minimum=0.0)
            if probability > 1:
                raise ValueError("probability must be within [0, 1]")
        event_id = str(uuid.uuid4())
        execution_epoch = signal_bar_epoch + self.granularity_seconds
        if action in {"ENTER_LONG", "ENTER_SHORT"} and not accepted and not reasons:
            raise ValueError("rejected entry decisions must include reason_codes")
        status = "ACCEPTED" if accepted else ("NO_TRADE" if action == "NO_TRADE" else "REJECTED")
        record = {
            "schema": SCHEMA,
            "record_type": "decision",
            "event_id": event_id,
            "timestamp_utc": _epoch_iso(execution_epoch),
            "symbol": self.symbol,
            "strategy": strategy.strip(),
            "fold_id": fold_id.strip(),
            "granularity_seconds": self.granularity_seconds,
            "action": action,
            "decision_status": status,
            "reason_codes": reasons,
            "signal_bar_epoch": signal_bar_epoch,
            "execution_bar_epoch": execution_epoch,
            "signal_timestamp_utc": _epoch_iso(execution_epoch),
            "expected_entry_timestamp_utc": _epoch_iso(execution_epoch),
            "hmm_regime_state": hmm_regime_state,
            "probability": probability,
            "data_sha256": self.data_sha256,
            "model_config_sha256": config_hash,
            "strategy_code_sha256": self.strategy_code_sha256,
        }
        self._append(record)
        self._decision_count += 1
        self._strategies.add(strategy.strip())
        self._fold_ids.add(fold_id.strip())
        self._config_hashes.add(config_hash)
        if accepted:
            self._accepted_decisions[event_id] = {
                "action": action,
                "signal_bar_epoch": signal_bar_epoch,
                "execution_bar_epoch": execution_epoch,
                "hmm_regime_state": hmm_regime_state,
                "symbol": self.symbol,
                "strategy": strategy.strip(),
                "fold_id": fold_id.strip(),
                "model_config_sha256": config_hash,
                "strategy_code_sha256": self.strategy_code_sha256,
            }
        return event_id

    def cancel_decision(
        self,
        *,
        decision_event_id: str,
        cancellation_epoch: int,
        reason_codes: Iterable[str],
    ) -> str:
        """Record an execution-time cancellation separately from the earlier signal decision.

        The model decision remains timestamped at candle N-1. This cancellation event
        may inspect candle N's open/entry geometry and must be timestamped at N; it
        cannot rewrite the earlier decision as though the open were already known.
        """
        decision = self._accepted_decisions.get(decision_event_id)
        if decision is None:
            raise ValueError("cancellation must reference a preceding accepted decision")
        if isinstance(cancellation_epoch, bool) or not isinstance(cancellation_epoch, int):
            raise ValueError("cancellation_epoch must be an integer UTC epoch")
        if cancellation_epoch != decision["execution_bar_epoch"]:
            raise ValueError("cancellation must occur at the scheduled next-bar execution epoch")
        reasons = list(reason_codes)
        if not reasons or any(not isinstance(item, str) or not item.strip() for item in reasons):
            raise ValueError("cancellation requires non-empty reason_codes")
        record = {
            "schema": SCHEMA,
            "record_type": "decision_cancelled",
            "event_id": str(uuid.uuid4()),
            "decision_event_id": decision_event_id,
            "timestamp_utc": _epoch_iso(cancellation_epoch),
            "cancellation_epoch": cancellation_epoch,
            "symbol": decision["symbol"],
            "strategy": decision["strategy"],
            "fold_id": decision["fold_id"],
            "granularity_seconds": self.granularity_seconds,
            "reason_codes": reasons,
            "signal_bar_epoch": decision["signal_bar_epoch"],
            "execution_bar_epoch": decision["execution_bar_epoch"],
            "hmm_regime_state": decision["hmm_regime_state"],
            "data_sha256": self.data_sha256,
            "model_config_sha256": decision["model_config_sha256"],
            "strategy_code_sha256": decision.get("strategy_code_sha256"),
        }
        self._append(record)
        self._cancel_count += 1
        del self._accepted_decisions[decision_event_id]
        return record["event_id"]

    def record_trade(
        self,
        *,
        decision_event_id: str,
        entry_epoch: int,
        exit_timestamp: str | datetime,
        entry_price: float,
        exit_price: float,
        initial_risk_cash: float,
        gross_pnl_cash: float,
        spread_cost_cash: float,
        slippage_cost_cash: float,
        commission_cost_cash: float = 0.0,
        spread_pips: float | None = None,
        slippage_bps: float | None = None,
        entry_reference_price: float | None = None,
        exit_reference_price: float | None = None,
        entry_spread_cost_cash: float | None = None,
        exit_spread_cost_cash: float | None = None,
        entry_slippage_cost_cash: float | None = None,
        exit_slippage_cost_cash: float | None = None,
        stop_reference_price: float | None = None,
        target_reference_price: float | None = None,
        exit_reason: str | None = None,
        cost_profile_status: str | None = None,
        cost_source_sha256: str | None = None,
        instrument_source_sha256: str | None = None,
    ) -> str:
        """Append a closed simulated trade using realized simulator outputs.

        Cash PnL/costs must be computed by the strategy's replay adapter. This method
        computes cost_r, net_pnl_cash, gross R and net R; it does not invent costs.
        """
        decision = self._accepted_decisions.get(decision_event_id)
        if decision is None:
            raise ValueError("trade must reference a preceding accepted decision event")
        if decision["action"] not in {"ENTER_LONG", "ENTER_SHORT"}:
            raise ValueError("NO_TRADE decisions cannot create trades")
        if isinstance(entry_epoch, bool) or not isinstance(entry_epoch, int):
            raise ValueError("entry_epoch must be integer UTC epoch seconds")
        if entry_epoch != decision["execution_bar_epoch"]:
            raise ValueError("entry must execute at the next candle open after the signal candle")
        if entry_epoch % self.granularity_seconds:
            raise ValueError("entry_epoch must align to the candle boundary")
        exit_dt = _aware_utc(exit_timestamp, "exit_timestamp")
        if exit_dt.timestamp() <= entry_epoch:
            raise ValueError("exit timestamp must be after entry timestamp")
        entry = _finite_number(entry_price, "entry_price", minimum=0.0, strict=True)
        exit_ = _finite_number(exit_price, "exit_price", minimum=0.0, strict=True)
        risk = _finite_number(initial_risk_cash, "initial_risk_cash", minimum=0.0, strict=True)
        gross = _finite_number(gross_pnl_cash, "gross_pnl_cash")
        spread = _finite_number(spread_cost_cash, "spread_cost_cash", minimum=0.0)
        slippage = _finite_number(slippage_cost_cash, "slippage_cost_cash", minimum=0.0)
        commission = _finite_number(commission_cost_cash, "commission_cost_cash", minimum=0.0)
        if spread_pips is not None:
            spread_pips = _finite_number(spread_pips, "spread_pips", minimum=0.0)
        if slippage_bps is not None:
            slippage_bps = _finite_number(slippage_bps, "slippage_bps", minimum=0.0)
        optional_prices = {}
        for name, value in (
            ("entry_reference_price", entry_reference_price),
            ("exit_reference_price", exit_reference_price),
            ("stop_reference_price", stop_reference_price),
            ("target_reference_price", target_reference_price),
        ):
            optional_prices[name] = (
                _finite_number(value, name, minimum=0.0, strict=True) if value is not None else None
            )
        optional_costs = {}
        for name, value in (
            ("entry_spread_cost_cash", entry_spread_cost_cash),
            ("exit_spread_cost_cash", exit_spread_cost_cash),
            ("entry_slippage_cost_cash", entry_slippage_cost_cash),
            ("exit_slippage_cost_cash", exit_slippage_cost_cash),
        ):
            optional_costs[name] = _finite_number(value, name, minimum=0.0) if value is not None else None
        if all(optional_costs[name] is not None for name in ("entry_spread_cost_cash", "exit_spread_cost_cash")):
            if abs(float(optional_costs["entry_spread_cost_cash"]) + float(optional_costs["exit_spread_cost_cash"]) - spread) > 1e-9:
                raise ValueError("entry/exit spread costs must reconcile to spread_cost_cash")
        if all(optional_costs[name] is not None for name in ("entry_slippage_cost_cash", "exit_slippage_cost_cash")):
            if abs(float(optional_costs["entry_slippage_cost_cash"]) + float(optional_costs["exit_slippage_cost_cash"]) - slippage) > 1e-9:
                raise ValueError("entry/exit slippage costs must reconcile to slippage_cost_cash")
        if exit_reason is not None and (not isinstance(exit_reason, str) or not exit_reason.strip()):
            raise ValueError("exit_reason must be non-empty when supplied")
        if cost_profile_status is not None and cost_profile_status not in {"VERIFIED", "EXPLORATORY_UNVERIFIED"}:
            raise ValueError("cost_profile_status is invalid")
        for digest_name, digest in (("cost_source_sha256", cost_source_sha256), ("instrument_source_sha256", instrument_source_sha256)):
            if digest is not None:
                _validate_digest(digest, digest_name)
        total_cost = spread + slippage + commission
        net_pnl = gross - total_cost
        r_gross = gross / risk
        cost_r = total_cost / risk
        net_r = net_pnl / risk
        event_id = str(uuid.uuid4())
        entry_dt = datetime.fromtimestamp(entry_epoch, timezone.utc)
        record = {
            "schema": SCHEMA,
            "record_type": "trade_closed",
            "event_id": event_id,
            "trade_id": str(uuid.uuid4()),
            "decision_event_id": decision_event_id,
            "timestamp_utc": _iso(entry_dt),
            "symbol": self.symbol,
            "strategy": decision["strategy"],
            "fold_id": decision["fold_id"],
            "granularity_seconds": self.granularity_seconds,
            "direction": "LONG" if decision["action"] == "ENTER_LONG" else "SHORT",
            "signal_timestamp_utc": _epoch_iso(decision["execution_bar_epoch"]),
            "entry_timestamp_utc": _iso(entry_dt),
            "exit_timestamp_utc": _iso(exit_dt),
            "signal_bar_epoch": decision["signal_bar_epoch"],
            "entry_bar_epoch": entry_epoch,
            "hmm_regime_state": decision["hmm_regime_state"],
            "entry_price": entry,
            "exit_price": exit_,
            "entry_reference_price": optional_prices["entry_reference_price"],
            "exit_reference_price": optional_prices["exit_reference_price"],
            "stop_reference_price": optional_prices["stop_reference_price"],
            "target_reference_price": optional_prices["target_reference_price"],
            "spread_pips": spread_pips,
            "slippage_bps": slippage_bps,
            "spread_cost_cash": spread,
            "slippage_cost_cash": slippage,
            "entry_spread_cost_cash": optional_costs["entry_spread_cost_cash"],
            "exit_spread_cost_cash": optional_costs["exit_spread_cost_cash"],
            "entry_slippage_cost_cash": optional_costs["entry_slippage_cost_cash"],
            "exit_slippage_cost_cash": optional_costs["exit_slippage_cost_cash"],
            "commission_cost_cash": commission,
            "exit_reason": exit_reason,
            "cost_profile_status": cost_profile_status,
            "cost_source_sha256": cost_source_sha256,
            "instrument_source_sha256": instrument_source_sha256,
            "total_cost_cash": total_cost,
            "initial_risk_cash": risk,
            "gross_pnl_cash": gross,
            "net_pnl_cash": net_pnl,
            "r_gross": r_gross,
            "cost_r": cost_r,
            "r_multiple": net_r,
            "data_sha256": self.data_sha256,
            "model_config_sha256": decision["model_config_sha256"],
            "strategy_code_sha256": decision.get("strategy_code_sha256"),
        }
        self._append(record)
        self._trade_count += 1
        del self._accepted_decisions[decision_event_id]
        return event_id

    def close(self) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("ledger is already closed")
        if self._accepted_decisions:
            raise RuntimeError(f"cannot seal ledger with {len(self._accepted_decisions)} accepted decision(s) lacking a closed trade record")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        self._closed = True
        raw_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        manifest = {
            "schema": "aurelia.audited_trade_ledger_manifest.v1",
            "ledger_file": self.path.name,
            "ledger_sha256": raw_hash,
            "head_record_sha256": self._head_hash,
            "decision_record_count": self._decision_count,
            "closed_trade_record_count": self._trade_count,
            "cancelled_entry_count": self._cancel_count,
            "symbol": self.symbol,
            "strategy_names": sorted(self._strategies),
            "fold_ids": sorted(self._fold_ids),
            "model_config_sha256s": sorted(self._config_hashes),
            "strategy_code_sha256": self.strategy_code_sha256,
            "granularity_seconds": self.granularity_seconds,
            "data_sha256": self.data_sha256,
            "created_at_utc": _iso(self._created_at_utc),
            "sealed_at_utc": _iso(datetime.now(timezone.utc)),
            "integrity_note": "SHA-256 proves consistency against this manifest after its digest is independently anchored; it cannot prove that pre-hash events were not omitted.",
        }
        manifest_path = self.path.with_suffix(self.path.suffix + ".manifest.json")
        if manifest_path.exists():
            raise FileExistsError(f"refusing to overwrite existing ledger manifest: {manifest_path}")
        temp_path = manifest_path.with_name(manifest_path.name + ".tmp")
        temp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temp_path, manifest_path)
        return manifest

    def __enter__(self) -> "AuditedLedgerWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._closed:
            if exc_type is None:
                self.close()
            else:
                self._stream.flush()
                os.fsync(self._stream.fileno())
                self._stream.close()
                self._closed = True


def verify_ledger(path: str | Path, manifest_path: str | Path | None = None) -> dict[str, Any]:
    ledger_path = Path(path)
    previous: str | None = None
    decisions: dict[str, dict[str, Any]] = {}
    decision_count = 0
    trade_count = 0
    cancellation_count = 0
    observed_code_hashes: set[str] = set()
    observed_data_hashes: set[str] = set()
    with ledger_path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.endswith("\n") or not line.strip():
                raise ValueError(f"line {line_no}: blank or unterminated JSONL record")
            try:
                record = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {x}")))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"line {line_no}: invalid JSON record") from exc
            if not isinstance(record, dict) or record.get("schema") != SCHEMA:
                raise ValueError(f"line {line_no}: invalid record schema")
            observed_hash = record.get("record_sha256")
            observed_previous = record.get("previous_record_sha256")
            if observed_previous != previous:
                raise ValueError(f"line {line_no}: previous-record hash chain mismatch")
            without_hash = dict(record)
            without_hash.pop("record_sha256", None)
            expected_hash = _sha256(_canonical(without_hash))
            if observed_hash != expected_hash:
                raise ValueError(f"line {line_no}: record hash mismatch")
            if record.get("record_type") == "decision":
                decision_count += 1
                granularity = record.get("granularity_seconds")
                if granularity not in (60, 900) or record.get("execution_bar_epoch") != record.get("signal_bar_epoch") + granularity:
                    raise ValueError(f"line {line_no}: decision does not respect next-bar execution timing")
                expected_decision_utc = _epoch_iso(int(record["execution_bar_epoch"]))
                if record.get("timestamp_utc") != expected_decision_utc or record.get("signal_timestamp_utc") != expected_decision_utc:
                    raise ValueError(f"line {line_no}: signal timestamp must be the signal candle close / next-bar open boundary")
                if record.get("expected_entry_timestamp_utc") != expected_decision_utc:
                    raise ValueError(f"line {line_no}: expected entry timestamp must match the next-bar open boundary")
                if record.get("decision_status") == "ACCEPTED":
                    decisions[record["event_id"]] = record
            elif record.get("record_type") == "decision_cancelled":
                cancellation_count += 1
                decision_id = record.get("decision_event_id")
                decision = decisions.get(decision_id)
                if decision is None:
                    raise ValueError(f"line {line_no}: cancellation has no preceding accepted decision")
                if record.get("cancellation_epoch") != decision.get("execution_bar_epoch"):
                    raise ValueError(f"line {line_no}: cancellation is not at the scheduled next-bar execution epoch")
                if record.get("signal_bar_epoch") != decision.get("signal_bar_epoch"):
                    raise ValueError(f"line {line_no}: cancellation signal timestamp mismatch")
                if record.get("timestamp_utc") != _epoch_iso(int(record["cancellation_epoch"])):
                    raise ValueError(f"line {line_no}: cancellation timestamp does not match cancellation epoch")
                if record.get("hmm_regime_state") != decision.get("hmm_regime_state"):
                    raise ValueError(f"line {line_no}: cancellation regime state mismatch")
                if record.get("symbol") != decision.get("symbol") or record.get("strategy") != decision.get("strategy") or record.get("fold_id") != decision.get("fold_id"):
                    raise ValueError(f"line {line_no}: cancellation instrument/strategy/fold mismatch")
                if record.get("model_config_sha256") != decision.get("model_config_sha256"):
                    raise ValueError(f"line {line_no}: cancellation model/config hash mismatch")
                if record.get("data_sha256") != decision.get("data_sha256"):
                    raise ValueError(f"line {line_no}: cancellation data hash mismatch")
                if record.get("strategy_code_sha256") != decision.get("strategy_code_sha256"):
                    raise ValueError(f"line {line_no}: cancellation strategy-code hash mismatch")
                reasons = record.get("reason_codes")
                if not isinstance(reasons, list) or not reasons or any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
                    raise ValueError(f"line {line_no}: cancellation reasons are missing")
                decisions.pop(decision_id, None)
            elif record.get("record_type") == "trade_closed":
                trade_count += 1
                decision_id = record.get("decision_event_id")
                decision = decisions.get(decision_id)
                if decision is None:
                    raise ValueError(f"line {line_no}: trade has no preceding accepted decision")
                if record.get("entry_bar_epoch") != decision.get("execution_bar_epoch"):
                    raise ValueError(f"line {line_no}: lookahead/entry-bar timing mismatch")
                granularity = record.get("granularity_seconds")
                if granularity not in (60, 900) or decision.get("granularity_seconds") != granularity:
                    raise ValueError(f"line {line_no}: invalid or inconsistent candle granularity")
                if record.get("entry_bar_epoch") != record.get("signal_bar_epoch") + granularity:
                    raise ValueError(f"line {line_no}: entry is not the next candle after the signal candle")
                if record.get("signal_timestamp_utc") != _epoch_iso(int(record["entry_bar_epoch"])):
                    raise ValueError(f"line {line_no}: signal timestamp is not the signal-close/next-bar-open boundary")
                if record.get("entry_timestamp_utc") != _epoch_iso(int(record["entry_bar_epoch"])):
                    raise ValueError(f"line {line_no}: entry timestamp does not match entry candle open")
                if record.get("hmm_regime_state") != decision.get("hmm_regime_state"):
                    raise ValueError(f"line {line_no}: regime state mismatch with decision")
                if record.get("strategy") != decision.get("strategy") or record.get("fold_id") != decision.get("fold_id"):
                    raise ValueError(f"line {line_no}: strategy/fold mismatch with decision")
                if record.get("strategy_code_sha256") != decision.get("strategy_code_sha256"):
                    raise ValueError(f"line {line_no}: strategy-code hash mismatch with decision")
                if record.get("data_sha256") != decision.get("data_sha256"):
                    raise ValueError(f"line {line_no}: data hash mismatch with decision")
                if record.get("model_config_sha256") != decision.get("model_config_sha256"):
                    raise ValueError(f"line {line_no}: model/config hash mismatch with decision")
                numeric = ("entry_price", "exit_price", "initial_risk_cash", "gross_pnl_cash", "spread_cost_cash",
                           "slippage_cost_cash", "commission_cost_cash", "total_cost_cash", "net_pnl_cash",
                           "r_gross", "cost_r", "r_multiple")
                for key in numeric:
                    value = record.get(key)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                        raise ValueError(f"line {line_no}: invalid numeric {key}")
                optional_numeric = (
                    "entry_reference_price", "exit_reference_price", "stop_reference_price",
                    "target_reference_price", "entry_spread_cost_cash", "exit_spread_cost_cash",
                    "entry_slippage_cost_cash", "exit_slippage_cost_cash",
                )
                for key in optional_numeric:
                    value = record.get(key)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                        raise ValueError(f"line {line_no}: invalid optional numeric {key}")
                    if value is not None and key.endswith("_cost_cash") and float(value) < 0:
                        raise ValueError(f"line {line_no}: optional cost cannot be negative: {key}")
                    if value is not None and key.endswith("_price") and float(value) <= 0:
                        raise ValueError(f"line {line_no}: optional reference price must be positive: {key}")
                for digest_key in ("cost_source_sha256", "instrument_source_sha256"):
                    value = record.get(digest_key)
                    if value is not None and not SHA256_RE.fullmatch(str(value)):
                        raise ValueError(f"line {line_no}: invalid {digest_key}")
                if record.get("exit_reason") is not None and (not isinstance(record["exit_reason"], str) or not record["exit_reason"].strip()):
                    raise ValueError(f"line {line_no}: invalid exit_reason")
                if all(record.get(key) is not None for key in ("entry_spread_cost_cash", "exit_spread_cost_cash")):
                    if abs(float(record["entry_spread_cost_cash"]) + float(record["exit_spread_cost_cash"]) - float(record["spread_cost_cash"])) > 1e-9:
                        raise ValueError(f"line {line_no}: entry/exit spread costs do not reconcile")
                if all(record.get(key) is not None for key in ("entry_slippage_cost_cash", "exit_slippage_cost_cash")):
                    if abs(float(record["entry_slippage_cost_cash"]) + float(record["exit_slippage_cost_cash"]) - float(record["slippage_cost_cash"])) > 1e-9:
                        raise ValueError(f"line {line_no}: entry/exit slippage costs do not reconcile")
                risk = float(record["initial_risk_cash"])
                total_cost = float(record["spread_cost_cash"]) + float(record["slippage_cost_cash"]) + float(record["commission_cost_cash"])
                if risk <= 0 or abs(float(record["total_cost_cash"]) - total_cost) > 1e-9:
                    raise ValueError(f"line {line_no}: invalid risk or cost totals")
                if abs(float(record["net_pnl_cash"]) - (float(record["gross_pnl_cash"]) - total_cost)) > 1e-9:
                    raise ValueError(f"line {line_no}: net PnL does not reconcile to gross PnL and costs")
                if abs(float(record["r_gross"]) - float(record["gross_pnl_cash"]) / risk) > 1e-9:
                    raise ValueError(f"line {line_no}: gross R does not reconcile")
                if abs(float(record["cost_r"]) - total_cost / risk) > 1e-9:
                    raise ValueError(f"line {line_no}: cost R does not reconcile")
                if abs(float(record["r_multiple"]) - float(record["net_pnl_cash"]) / risk) > 1e-9:
                    raise ValueError(f"line {line_no}: net R does not reconcile")
                decisions.pop(decision_id, None)
            else:
                raise ValueError(f"line {line_no}: unknown record_type")
            for key in ("data_sha256", "model_config_sha256"):
                if not SHA256_RE.fullmatch(str(record.get(key, ""))):
                    raise ValueError(f"line {line_no}: invalid {key}")
            observed_data_hashes.add(str(record["data_sha256"]))
            code_hash = record.get("strategy_code_sha256")
            if code_hash is not None:
                if not SHA256_RE.fullmatch(str(code_hash)):
                    raise ValueError(f"line {line_no}: invalid strategy_code_sha256")
                observed_code_hashes.add(str(code_hash))
            previous = observed_hash
    if len(observed_code_hashes) > 1:
        raise ValueError("ledger mixes different strategy-code bundle hashes")
    if len(observed_data_hashes) > 1:
        raise ValueError("ledger mixes different historical-data hashes")
    if decision_count == 0:
        raise ValueError("ledger has no decision records")
    if decisions:
        raise ValueError(f"ledger has {len(decisions)} accepted decision(s) without a closed trade record")
    file_hash = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    result: dict[str, Any] = {
        "ledger_sha256": file_hash,
        "head_record_sha256": previous,
        "decision_record_count": decision_count,
        "closed_trade_record_count": trade_count,
        "cancelled_entry_count": cancellation_count,
        "strategy_code_sha256": next(iter(observed_code_hashes), None),
        "data_sha256": next(iter(observed_data_hashes), None),
        "integrity_verified": True,
    }
    resolved_manifest = Path(manifest_path) if manifest_path else ledger_path.with_suffix(ledger_path.suffix + ".manifest.json")
    if resolved_manifest.exists():
        manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
        for key, observed in (
            ("ledger_sha256", file_hash),
            ("head_record_sha256", previous),
            ("decision_record_count", decision_count),
            ("closed_trade_record_count", trade_count),
            ("cancelled_entry_count", cancellation_count),
            ("strategy_code_sha256", next(iter(observed_code_hashes), None)),
            ("data_sha256", next(iter(observed_data_hashes), None)),
        ):
            if manifest.get(key) != observed:
                raise ValueError(f"manifest {key} mismatch")
        result["manifest_verified"] = True
    else:
        result["manifest_verified"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a hash-chained AURELIA simulator JSONL ledger.")
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify_ledger(args.ledger, args.manifest)
    except Exception as exc:
        print("AUDITED_LEDGER=INVALID")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2
    print("AUDITED_LEDGER=VERIFIED")
    for key, value in result.items():
        print(f"{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
