"""Persistent account-scoped daily-loss and consecutive-loss guard.

Defaults are policy controls, not evidence of profitability. A tripped guard
persists across restarts and UTC day boundaries; an authorized operator must
remove the halt through a reviewed reset procedure.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class RiskGuardDecision:
    allowed: bool
    reason: str | None = None


class PersistentDailyRiskGuard:
    """Track settled P&L per verified account, failing closed on corrupt state."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_daily_drawdown_fraction: float = 0.03,
        max_consecutive_losses: int = 3,
    ) -> None:
        if not isfinite(max_daily_drawdown_fraction) or not 0 < max_daily_drawdown_fraction <= 0.10:
            raise ValueError("DAILY_DRAWDOWN_POLICY_INVALID")
        if isinstance(max_consecutive_losses, bool) or not isinstance(max_consecutive_losses, int) or max_consecutive_losses < 1:
            raise ValueError("CONSECUTIVE_LOSS_POLICY_INVALID")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_daily_drawdown_fraction = max_daily_drawdown_fraction
        self.max_consecutive_losses = max_consecutive_losses
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "version": 1, "account_key": None, "utc_day": None,
            "reference_equity": None, "realized_pnl": 0.0,
            "consecutive_losses": 0, "halted": False, "halt_reason": None,
        }
        self._load_error: str | None = None
        try:
            self._load()
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self._load_error = "DAILY_RISK_STATE_UNREADABLE"

    @staticmethod
    def account_key(account: Any) -> str:
        return "|".join(str(getattr(account, name, "")) for name in
                        ("loginid", "account_type", "currency", "environment"))

    @staticmethod
    def _utc_day(now: datetime) -> str:
        if now.tzinfo is None:
            raise ValueError("RISK_GUARD_TIME_MUST_BE_TIMEZONE_AWARE")
        return now.astimezone(timezone.utc).date().isoformat()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("halted"), bool):
            raise ValueError("DAILY_RISK_STATE_INVALID")
        if not isinstance(payload.get("consecutive_losses"), int):
            raise ValueError("DAILY_RISK_STATE_INVALID")
        if not isfinite(float(payload.get("realized_pnl", 0.0))):
            raise ValueError("DAILY_RISK_STATE_INVALID")
        self._state = payload

    def _save(self) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(self._state, handle, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)

    def _roll_day(self, *, account_key: str, equity: float, now: datetime) -> None:
        day = self._utc_day(now)
        previous_account = self._state.get("account_key")
        if previous_account and previous_account != account_key:
            self._state["halted"] = True
            self._state["halt_reason"] = "RISK_GUARD_ACCOUNT_IDENTITY_CHANGED"
            self._save()
            return
        previous_day = self._state.get("utc_day")
        if previous_day is None:
            self._state.update(account_key=account_key, utc_day=day, reference_equity=equity,
                               realized_pnl=0.0, consecutive_losses=0)
            self._save()
        elif previous_day != day and not self._state.get("halted", False):
            self._state.update(account_key=account_key, utc_day=day, reference_equity=equity,
                               realized_pnl=0.0, consecutive_losses=0, halt_reason=None)
            self._save()

    def check(self, *, account: Any, verified_equity: float,
              now: datetime | None = None) -> RiskGuardDecision:
        with self._lock:
            if self._load_error:
                return RiskGuardDecision(False, self._load_error)
            observed = now or datetime.now(timezone.utc)
            if not isfinite(verified_equity) or verified_equity <= 0:
                return RiskGuardDecision(False, "RISK_GUARD_EQUITY_INVALID")
            key = self.account_key(account)
            if not key.strip("|"):
                return RiskGuardDecision(False, "RISK_GUARD_ACCOUNT_IDENTITY_INVALID")
            self._roll_day(account_key=key, equity=verified_equity, now=observed)
            if self._state.get("halted"):
                return RiskGuardDecision(False, self._state.get("halt_reason") or "RISK_GUARD_HALTED")
            reference = self._state.get("reference_equity")
            if not isinstance(reference, (int, float)) or not isfinite(float(reference)) or reference <= 0:
                return RiskGuardDecision(False, "RISK_GUARD_REFERENCE_EQUITY_INVALID")
            return RiskGuardDecision(True)

    def record_settlement(self, *, account: Any, verified_pre_trade_equity: float,
                          net_pnl: float, now: datetime | None = None) -> RiskGuardDecision:
        with self._lock:
            if self._load_error:
                return RiskGuardDecision(False, self._load_error)
            observed = now or datetime.now(timezone.utc)
            if not isfinite(verified_pre_trade_equity) or verified_pre_trade_equity <= 0:
                return RiskGuardDecision(False, "RISK_GUARD_EQUITY_INVALID")
            if not isfinite(net_pnl):
                return RiskGuardDecision(False, "RISK_GUARD_SETTLEMENT_PNL_INVALID")
            key = self.account_key(account)
            self._roll_day(account_key=key, equity=verified_pre_trade_equity, now=observed)
            if self._state.get("halted"):
                return RiskGuardDecision(False, self._state.get("halt_reason") or "RISK_GUARD_HALTED")
            self._state["realized_pnl"] = float(self._state.get("realized_pnl", 0.0)) + net_pnl
            losses = int(self._state.get("consecutive_losses", 0))
            self._state["consecutive_losses"] = losses + 1 if net_pnl < 0 else (0 if net_pnl > 0 else losses)
            reference = float(self._state["reference_equity"])
            reason = None
            if self._state["realized_pnl"] <= -(reference * self.max_daily_drawdown_fraction):
                reason = "DAILY_DRAWDOWN_LIMIT_REACHED"
            elif self._state["consecutive_losses"] >= self.max_consecutive_losses:
                reason = "CONSECUTIVE_LOSS_LIMIT_REACHED"
            if reason:
                self._state["halted"] = True
                self._state["halt_reason"] = reason
            self._save()
            return RiskGuardDecision(not bool(reason), reason)
