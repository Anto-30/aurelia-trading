"""Persistent fail-closed daily drawdown and consecutive-loss controls.

The guard only records terminal broker outcomes after independent reconciliation.
It never authorizes live trading; it can only deny an otherwise-authorized order.
All risk-day boundaries are UTC and a tripped state survives process restarts.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Sequence


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("RISK_TIME_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def derive_utc_day_start_balance(
    *,
    current_balance: float,
    transactions: Sequence[dict[str, Any]],
    day_start_epoch: int,
    day_end_epoch: int,
    currency: str,
    maximum_transactions: int = 999,
    absolute_tolerance: float = 0.01,
) -> tuple[float, str]:
    """Reconstruct day-opening balance from a complete UTC-day broker statement.

    Statement rows must supply transaction_time, transaction_id/id, amount,
    balance_after and currency. Missing identity/currency or a truncated
    statement is UNKNOWN and blocks startup. A genuinely empty day returns the
    current broker balance as the baseline.
    """
    balance = _finite(current_balance)
    code = str(currency or "").strip().upper()
    if balance is None or balance <= 0:
        raise ValueError("DAILY_RISK_CURRENT_BALANCE_INVALID")
    if not code:
        raise ValueError("DAILY_RISK_CURRENCY_REQUIRED")
    if day_start_epoch < 0 or day_end_epoch < day_start_epoch:
        raise ValueError("DAILY_RISK_STATEMENT_WINDOW_INVALID")
    if not isinstance(transactions, Sequence) or isinstance(transactions, (str, bytes)):
        raise ValueError("DAILY_RISK_STATEMENT_INVALID")
    if len(transactions) >= maximum_transactions:
        raise ValueError("DAILY_RISK_STATEMENT_LIMIT_REACHED")
    if not transactions:
        return balance, "DERIV_CURRENT_BALANCE_NO_UTC_DAY_TRANSACTIONS"

    rows: list[tuple[int, str, float, float]] = []
    identifiers: set[str] = set()
    for item in transactions:
        if not isinstance(item, dict):
            raise ValueError("DAILY_RISK_STATEMENT_ROW_INVALID")
        stamp = _finite(item.get("transaction_time"))
        amount = _finite(item.get("amount"))
        after = _finite(item.get("balance_after"))
        txid = str(item.get("transaction_id") or item.get("id") or "").strip()
        row_currency = str(item.get("currency") or "").strip().upper()
        if stamp is None or amount is None or after is None or not txid or not row_currency:
            raise ValueError("DAILY_RISK_STATEMENT_FIELDS_UNVERIFIED")
        if not day_start_epoch <= int(stamp) <= day_end_epoch:
            raise ValueError("DAILY_RISK_STATEMENT_WINDOW_MISMATCH")
        if row_currency != code:
            raise ValueError("DAILY_RISK_STATEMENT_CURRENCY_MISMATCH")
        if txid in identifiers:
            raise ValueError("DAILY_RISK_STATEMENT_DUPLICATE_TRANSACTION")
        identifiers.add(txid)
        rows.append((int(stamp), txid, amount, after))

    rows.sort(key=lambda row: (row[0], row[1]))
    first = rows[0]
    reference = first[3] - first[2]
    if not math.isfinite(reference) or reference <= 0:
        raise ValueError("DAILY_RISK_REFERENCE_EQUITY_INVALID")
    for before, after in zip(rows, rows[1:]):
        expected = before[3] + after[2]
        if not math.isclose(expected, after[3], rel_tol=1e-6, abs_tol=absolute_tolerance):
            raise ValueError("DAILY_RISK_STATEMENT_BALANCE_CHAIN_BROKEN")
    tolerance = max(absolute_tolerance, abs(balance) * 1e-6)
    if not math.isclose(rows[-1][3], balance, rel_tol=1e-6, abs_tol=tolerance):
        raise ValueError("DAILY_RISK_STATEMENT_BALANCE_MISMATCH")
    return reference, "DERIV_STATEMENT_RECONSTRUCTED"


class PersistentDailyRiskGuard:
    """Durable 3% daily drawdown / 3-loss breaker, fail-closed on UNKNOWN."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path,
        *,
        max_daily_drawdown_pct: float = 0.03,
        max_consecutive_losses: int = 3,
        max_balance_age_seconds: float = 15.0,
    ) -> None:
        if not math.isfinite(max_daily_drawdown_pct) or not 0 < max_daily_drawdown_pct <= 0.10:
            raise ValueError("DAILY_RISK_DRAWDOWN_LIMIT_INVALID")
        if isinstance(max_consecutive_losses, bool) or max_consecutive_losses < 1:
            raise ValueError("DAILY_RISK_LOSS_STREAK_LIMIT_INVALID")
        if not math.isfinite(max_balance_age_seconds) or max_balance_age_seconds <= 0:
            raise ValueError("DAILY_RISK_BALANCE_AGE_LIMIT_INVALID")
        self.path = Path(path)
        self.max_daily_drawdown_pct = float(max_daily_drawdown_pct)
        self.max_consecutive_losses = int(max_consecutive_losses)
        self.max_balance_age_seconds = float(max_balance_age_seconds)
        self._lock = RLock()
        self._state: dict[str, Any] | None = None
        self._load_error: str | None = None
        if self.path.exists():
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or value.get("schema_version") != self.SCHEMA_VERSION:
                    raise ValueError("schema mismatch")
                self._state = value
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._load_error = type(exc).__name__

    @property
    def initialized(self) -> bool:
        return bool(self._state and self._state.get("initialized") is True and not self._load_error)

    @property
    def tripped(self) -> bool:
        return bool(self._state and self._state.get("tripped") is True) or self._load_error is not None

    def _save(self) -> None:
        if self._state is None:
            raise RuntimeError("DAILY_RISK_STATE_UNINITIALIZED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state, sort_keys=True, separators=(",", ":"), allow_nan=False)
        fd, temp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        except OSError as exc:
            self._load_error = type(exc).__name__
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise RuntimeError("DAILY_RISK_STATE_PERSISTENCE_FAILED") from exc

    def _decision(self, allowed: bool, reason: str | None) -> dict[str, Any]:
        state = self._state or {}
        ref = _finite(state.get("reference_balance"))
        balance = _finite(state.get("current_balance"))
        drawdown = max(0.0, (ref - balance) / ref) if ref and balance is not None else None
        realized = _finite(state.get("daily_realized_pnl"))
        streak = state.get("consecutive_losses")
        return {
            "allowed": allowed,
            "reason": reason,
            "daily_drawdown_pct": drawdown,
            "daily_realized_pnl": realized,
            "consecutive_losses": int(streak) if isinstance(streak, int) else None,
        }

    def _trip_locked(self, reason: str, now: datetime) -> dict[str, Any]:
        if self._state is None:
            self._state = {
                "schema_version": self.SCHEMA_VERSION,
                "initialized": False,
                "account_loginid": "",
                "currency": "",
                "utc_day": _utc(now).date().isoformat(),
                "reference_balance": None,
                "baseline_source": None,
                "current_balance": None,
                "daily_realized_pnl": 0.0,
                "consecutive_losses": 0,
                "settlements": {},
            }
        self._state["tripped"] = True
        self._state["reason"] = reason
        self._state["updated_at_utc"] = _utc(now).isoformat()
        try:
            self._save()
        except RuntimeError:
            pass
        return self._decision(False, reason)

    def initialize_day(
        self,
        *,
        account_loginid: str,
        currency: str,
        utc_day: str,
        reference_balance: float,
        baseline_source: str,
        now: datetime | None = None,
    ) -> bool:
        """Initialize a UTC day once; no same-day reset and no reset of a trip."""
        with self._lock:
            observed = _utc(now or datetime.now(timezone.utc))
            if self._load_error:
                raise RuntimeError("DAILY_RISK_STATE_UNREADABLE")
            loginid, cur = str(account_loginid or "").strip(), str(currency or "").strip().upper()
            ref = _finite(reference_balance)
            today = observed.date().isoformat()
            try:
                requested_day = datetime.strptime(utc_day, "%Y-%m-%d").date().isoformat()
            except (TypeError, ValueError) as exc:
                raise ValueError("DAILY_RISK_DAY_INVALID") from exc
            if requested_day != today:
                raise ValueError("DAILY_RISK_BASELINE_NOT_FOR_CURRENT_UTC_DAY")
            if not loginid or not cur or not str(baseline_source or "").strip():
                raise ValueError("DAILY_RISK_ACCOUNT_OR_BASELINE_SOURCE_MISSING")
            if ref is None or ref <= 0:
                raise ValueError("DAILY_RISK_REFERENCE_EQUITY_INVALID")
            prior = self._state
            if prior:
                if prior.get("account_loginid") != loginid or prior.get("currency") != cur:
                    raise RuntimeError("DAILY_RISK_ACCOUNT_BINDING_MISMATCH")
                prior_day = str(prior.get("utc_day") or "")
                if prior_day > today:
                    raise RuntimeError("DAILY_RISK_UTC_CLOCK_ROLLBACK")
                if prior.get("tripped"):
                    raise RuntimeError("DAILY_RISK_PRIOR_TRIP_REQUIRES_AUTHORIZED_RESET")
                if prior_day == today:
                    if prior.get("initialized") is not True:
                        raise RuntimeError("DAILY_RISK_STATE_UNINITIALIZED")
                    return False
                # Daily P&L/reference reset at UTC rollover; loss streak persists
                # across days to avoid accidental loss-streak erasure on restart.
                streak = int(prior.get("consecutive_losses", 0))
            else:
                streak = 0
            self._state = {
                "schema_version": self.SCHEMA_VERSION,
                "initialized": True,
                "account_loginid": loginid,
                "currency": cur,
                "utc_day": today,
                "reference_balance": ref,
                "baseline_source": baseline_source,
                "current_balance": ref,
                "daily_realized_pnl": 0.0,
                "consecutive_losses": streak,
                "settlements": {},
                "tripped": streak >= self.max_consecutive_losses,
                "reason": "CONSECUTIVE_LOSS_LIMIT" if streak >= self.max_consecutive_losses else None,
                "updated_at_utc": observed.isoformat(),
            }
            self._save()
            if self._state["tripped"]:
                raise RuntimeError("DAILY_RISK_CONSECUTIVE_LOSS_LIMIT")
            return True

    def permit(
        self,
        *,
        account_loginid: str,
        currency: str,
        current_balance: float,
        captured_at: datetime,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            observed = _utc(now or datetime.now(timezone.utc))
            if self._load_error:
                return self._decision(False, "DAILY_RISK_STATE_UNREADABLE")
            if not self.initialized or self._state is None:
                return self._decision(False, "DAILY_RISK_STATE_UNINITIALIZED")
            state = self._state
            if state.get("tripped"):
                return self._decision(False, str(state.get("reason") or "DAILY_RISK_TRIPPED"))
            if state.get("account_loginid") != account_loginid or state.get("currency") != str(currency).strip().upper():
                return self._trip_locked("DAILY_RISK_ACCOUNT_BINDING_MISMATCH", observed)
            if state.get("utc_day") != observed.date().isoformat():
                return self._decision(False, "DAILY_RISK_DAY_ROLLOVER_NOT_INITIALIZED")
            try:
                captured = _utc(captured_at)
            except ValueError:
                return self._decision(False, "BALANCE_CAPTURE_TIME_INVALID")
            age = (observed - captured).total_seconds()
            if age < 0 or age > self.max_balance_age_seconds:
                return self._decision(False, "BALANCE_SNAPSHOT_STALE")
            balance = _finite(current_balance)
            if balance is None or balance < 0:
                return self._decision(False, "BROKER_BALANCE_INVALID")
            state["current_balance"] = balance
            drawdown = self._drawdown(balance)
            state["updated_at_utc"] = observed.isoformat()
            if drawdown >= self.max_daily_drawdown_pct:
                return self._trip_locked("DAILY_DRAWDOWN_LIMIT", observed)
            if int(state.get("consecutive_losses", 0)) >= self.max_consecutive_losses:
                return self._trip_locked("CONSECUTIVE_LOSS_LIMIT", observed)
            self._save()
            return self._decision(True, None)

    def _drawdown(self, balance: float) -> float:
        assert self._state is not None
        reference = float(self._state["reference_balance"])
        pnl = float(self._state["daily_realized_pnl"])
        balance_loss = max(0.0, reference - balance)
        realized_loss = max(0.0, -pnl)
        return max(balance_loss, realized_loss) / reference

    def trip(self, reason: str, *, now: datetime | None = None) -> dict[str, Any]:
        with self._lock:
            return self._trip_locked(str(reason or "DAILY_RISK_TRIPPED"), _utc(now or datetime.now(timezone.utc)))

    def record_closed_trade(
        self,
        *,
        intent_id: str,
        contract_id: str,
        broker_transaction_id: str,
        account_loginid: str,
        currency: str,
        net_pnl: float,
        post_balance: float,
        closed_at: datetime,
        terminal: bool,
        reconciled: bool,
    ) -> dict[str, Any]:
        with self._lock:
            observed = _utc(closed_at)
            if self._load_error:
                return self._decision(False, "DAILY_RISK_STATE_PERSISTENCE_UNAVAILABLE")
            if not terminal or not reconciled or not intent_id or not contract_id or not broker_transaction_id:
                return self._trip_locked("SETTLEMENT_OR_RECONCILIATION_UNVERIFIED", observed)
            pnl, balance = _finite(net_pnl), _finite(post_balance)
            if pnl is None or balance is None or balance < 0:
                return self._trip_locked("SETTLEMENT_ECONOMICS_INVALID", observed)
            if not self.initialized or self._state is None:
                return self._trip_locked("DAILY_RISK_STATE_UNINITIALIZED", observed)
            state = self._state
            if state.get("tripped"):
                return self._decision(False, str(state.get("reason") or "DAILY_RISK_TRIPPED"))
            if state.get("account_loginid") != account_loginid or state.get("currency") != str(currency).strip().upper():
                return self._trip_locked("DAILY_RISK_ACCOUNT_BINDING_MISMATCH", observed)
            if state.get("utc_day") != observed.date().isoformat():
                return self._trip_locked("DAILY_RISK_DAY_ROLLOVER_NOT_INITIALIZED", observed)
            key = str(contract_id)
            settlement = {
                "intent_id": str(intent_id),
                "broker_transaction_id": str(broker_transaction_id),
                "net_pnl": pnl,
            }
            prior = state.setdefault("settlements", {}).get(key)
            if prior is not None:
                if prior == settlement:
                    return self._decision(not state.get("tripped"), state.get("reason"))
                return self._trip_locked("CONFLICTING_SETTLEMENT_REPLAY", observed)
            state["settlements"][key] = settlement
            state["daily_realized_pnl"] = float(state.get("daily_realized_pnl", 0.0)) + pnl
            state["consecutive_losses"] = int(state.get("consecutive_losses", 0)) + 1 if pnl < 0 else 0
            state["current_balance"] = balance
            state["updated_at_utc"] = observed.isoformat()
            if self._drawdown(balance) >= self.max_daily_drawdown_pct:
                return self._trip_locked("DAILY_DRAWDOWN_LIMIT", observed)
            if int(state["consecutive_losses"]) >= self.max_consecutive_losses:
                return self._trip_locked("CONSECUTIVE_LOSS_LIMIT", observed)
            self._save()
            return self._decision(True, None)
