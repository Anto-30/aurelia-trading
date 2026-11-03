"""Authenticated Deriv state verification with no trading/proposal requests.

This verifier only bootstraps an OTP session, reads balance/portfolio/statement,
checks persisted local risk/kill-switch files, and writes local hash-linked
evidence. It never requests a proposal and never sends buy, sell, cancel,
contract-update, or other capital-moving instructions.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence
from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager
from runtime.core.daily_risk import derive_utc_day_start_balance
from runtime.core.events import sha256
from runtime.core.release_gate import read_live_release
from runtime.core.runtime_config import load_config_hash
from runtime.core.secrets import get_optional_secret


OUTPUT = Path(
    os.getenv("AURELIA_DERIV_READONLY_EVIDENCE_OUT", "").strip()
    or "artifacts/deriv_read_only_state.json"
)
DAILY_RISK_DEFAULT = "/var/lib/aurelia/daily-risk.json"
KILL_SWITCH_DEFAULT = "/var/lib/aurelia/kill-switch-state.json"
STATEMENT_LIMIT = 999


class ReadOnlyVerificationError(RuntimeError):
    """A required broker or persisted-state observation is unknown/inconsistent."""


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        from math import isfinite
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


async def collect_read_only_snapshot(
    adapter,
    *,
    expected_loginid: str,
    expected_currency: str,
    now: datetime | None = None,
    statement_limit: int = STATEMENT_LIMIT,
) -> dict[str, Any]:
    """Read one stable broker snapshot using only balance/portfolio/statement."""
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ReadOnlyVerificationError("DERIV_READONLY_TIMEZONE_REQUIRED")
    if isinstance(statement_limit, bool) or not isinstance(statement_limit, int):
        raise ReadOnlyVerificationError("DERIV_READONLY_STATEMENT_LIMIT_INVALID")
    if not 1 <= statement_limit <= 999:
        raise ReadOnlyVerificationError("DERIV_READONLY_STATEMENT_LIMIT_INVALID")

    account = await adapter.connect()
    if (
        account.loginid != expected_loginid
        or account.account_type != "real"
        or account.environment != "real"
        or account.currency.strip().upper() != expected_currency.strip().upper()
    ):
        raise ReadOnlyVerificationError("DERIV_READONLY_ACCOUNT_BINDING_MISMATCH")

    before = await adapter.get_balance()
    if (
        not before.is_valid()
        or before.account != account
        or before.currency.strip().upper() != expected_currency.strip().upper()
    ):
        raise ReadOnlyVerificationError("DERIV_READONLY_INITIAL_BALANCE_UNVERIFIED")

    open_positions = await adapter.portfolio()
    if not isinstance(open_positions, list):
        raise ReadOnlyVerificationError("DERIV_READONLY_PORTFOLIO_INVALID")

    utc_now = observed_at.astimezone(timezone.utc)
    day_start = datetime(
        utc_now.year, utc_now.month, utc_now.day, tzinfo=timezone.utc
    )
    statement = await adapter.statement(
        limit=statement_limit,
        date_from=int(day_start.timestamp()),
        date_to=int(utc_now.timestamp()),
    )
    if not isinstance(statement, list):
        raise ReadOnlyVerificationError("DERIV_READONLY_STATEMENT_INVALID")
    if len(statement) >= statement_limit:
        raise ReadOnlyVerificationError("DERIV_READONLY_STATEMENT_LIMIT_REACHED")

    after = await adapter.get_balance()
    if (
        not after.is_valid()
        or after.account != account
        or after.currency.strip().upper() != expected_currency.strip().upper()
    ):
        raise ReadOnlyVerificationError("DERIV_READONLY_FINAL_BALANCE_UNVERIFIED")
    if (
        not isclose(before.balance, after.balance, rel_tol=0.0, abs_tol=0.01)
        or not isclose(
            before.available_balance,
            after.available_balance,
            rel_tol=0.0,
            abs_tol=0.01,
        )
    ):
        raise ReadOnlyVerificationError("DERIV_READONLY_BALANCE_CHANGED_DURING_SNAPSHOT")

    try:
        day_opening_balance, baseline_source = derive_utc_day_start_balance(
            current_balance=after.balance,
            transactions=statement,
            day_start_epoch=int(day_start.timestamp()),
            day_end_epoch=int(utc_now.timestamp()),
            currency=account.currency,
            maximum_transactions=statement_limit,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReadOnlyVerificationError("DERIV_READONLY_STATEMENT_RECONCILIATION_FAILED") from exc

    return {
        "account_loginid": account.loginid,
        "account_type": account.account_type,
        "environment": account.environment,
        "currency": after.currency,
        "balance": after.balance,
        "available_balance": after.available_balance,
        "balance_captured_at_utc": after.captured_at.isoformat(),
        "day_opening_balance": day_opening_balance,
        "day_opening_balance_source": baseline_source,
        "open_positions_count": len(open_positions),
        "open_positions": open_positions,
        "statement_transaction_count": len(statement),
        "statement_window_start_utc": day_start.isoformat(),
        "statement_window_end_utc": utc_now.isoformat(),
        "balance_stable_across_snapshot": True,
        "read_api_calls": ["balance", "portfolio", "statement", "balance"],
        "trade_api_calls": [],
        "orders_submitted": 0,
        "capital_movement": False,
    }


def read_persistent_runtime_controls(
    *,
    account_loginid: str,
    currency: str,
    utc_day: str,
    daily_risk_path: str | Path,
    kill_switch_path: str | Path,
) -> dict[str, Any]:
    """Validate persistence files without changing or resetting either state."""
    daily_path = Path(daily_risk_path)
    kill_path = Path(kill_switch_path)
    if not daily_path.is_file() or not kill_path.is_file():
        raise ReadOnlyVerificationError("PERSISTENT_RISK_OR_KILL_SWITCH_STATE_MISSING")

    try:
        daily_raw = daily_path.read_bytes()
        kill_raw = kill_path.read_bytes()
        daily = json.loads(daily_raw.decode("utf-8"))
        kill = json.loads(kill_raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReadOnlyVerificationError("PERSISTENT_CONTROL_STATE_UNREADABLE") from exc

    if (
        not isinstance(daily, dict)
        or daily.get("schema_version") != 1
        or daily.get("initialized") is not True
        or daily.get("account_loginid") != account_loginid
        or str(daily.get("currency", "")).strip().upper() != currency.strip().upper()
        or daily.get("utc_day") != utc_day
        or not isinstance(daily.get("tripped"), bool)
    ):
        raise ReadOnlyVerificationError("PERSISTENT_DAILY_RISK_STATE_MISMATCH")

    updated = daily.get("updated_at_utc")
    try:
        parsed_daily_updated = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ReadOnlyVerificationError("PERSISTENT_DAILY_RISK_TIMESTAMP_INVALID") from exc
    if parsed_daily_updated.tzinfo is None:
        raise ReadOnlyVerificationError("PERSISTENT_DAILY_RISK_TIMESTAMP_INVALID")

    if (
        not isinstance(kill, dict)
        or kill.get("schema") != "aurelia.kill_switch_state.v1"
        or kill.get("state") not in {"STARTUP_LOCKED", "TRIPPED", "CLEARED"}
        or isinstance(kill.get("generation"), bool)
        or not isinstance(kill.get("generation"), int)
        or kill.get("generation") < 0
    ):
        raise ReadOnlyVerificationError("PERSISTENT_KILL_SWITCH_STATE_INVALID")
    try:
        parsed_kill_updated = datetime.fromisoformat(
            str(kill.get("updated_at_utc") or "").replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise ReadOnlyVerificationError("PERSISTENT_KILL_SWITCH_TIMESTAMP_INVALID") from exc
    if parsed_kill_updated.tzinfo is None:
        raise ReadOnlyVerificationError("PERSISTENT_KILL_SWITCH_TIMESTAMP_INVALID")

    return {
        "daily_risk_state_persisted": True,
        "daily_risk_state_sha256": hashlib.sha256(daily_raw).hexdigest(),
        "daily_risk_tripped": daily["tripped"],
        "daily_risk_reason": daily.get("reason"),
        "daily_risk_utc_day": daily["utc_day"],
        "kill_switch_state_persisted": True,
        "kill_switch_state_sha256": hashlib.sha256(kill_raw).hexdigest(),
        "kill_switch_state": kill["state"],
        "kill_switch_reason": kill.get("reason"),
        "kill_switch_generation": kill["generation"],
    }


async def run() -> int:
    lock_path = ROOT / "config" / "LIVE_LOCK.yaml"
    release = read_live_release(lock_path)
    if (
        release.live_trading_enabled
        or release.final_execution_authorization
        or release.live_execution_enabled
        or release.capital_plane_mode != "VERIFY_ONLY"
    ):
        print("DERIV_READONLY_STATE=BLOCKED")
        print("REASON=LIVE_LOCK_NOT_IN_EXPECTED_VERIFY_ONLY_STATE")
        return 2

    token = get_optional_secret("DERIV_AUTH_TOKEN") or get_optional_secret("DERIV_PAT")
    loginid = (
        os.getenv("DERIV_EXPECTED_LOGINID")
        or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "")
    ).strip()
    currency = os.getenv("DERIV_EXPECTED_CURRENCY", "").strip().upper()
    environment = os.getenv("DERIV_ENVIRONMENT", "").strip().lower()
    if not token or not loginid or not currency or environment != "real":
        print("DERIV_READONLY_STATE=BLOCKED")
        print("REASON=AUTHENTICATED_REAL_ACCOUNT_CONFIGURATION_MISSING")
        return 2
    if currency != "USD":
        print("DERIV_READONLY_STATE=BLOCKED")
        print("REASON=UNSUPPORTED_CURRENCY_FOR_CURRENT_RUNTIME_POLICY")
        return 2

    adapter: DerivAdapter | None = None
    try:
        manager = DerivSessionManager(
            expected_loginid=loginid,
            expected_environment="real",
            expected_currency=currency,
        )
        bootstrap = manager.bootstrap(
            bearer_token=token,
            app_id=get_optional_secret("DERIV_APP_ID") or None,
        )
        adapter = DerivAdapter(
            ws_url=bootstrap.websocket.url,
            expected_loginid=bootstrap.binding.loginid,
            expected_currency=currency,
            environment="real",
            auth_token="",
        )
        now = datetime.now(timezone.utc)
        snapshot = await collect_read_only_snapshot(
            adapter,
            expected_loginid=loginid,
            expected_currency=currency,
            now=now,
        )
        persisted = read_persistent_runtime_controls(
            account_loginid=loginid,
            currency=currency,
            utc_day=now.date().isoformat(),
            daily_risk_path=os.getenv("AURELIA_DAILY_RISK_PATH", DAILY_RISK_DEFAULT),
            kill_switch_path=os.getenv(
                "AURELIA_KILL_SWITCH_STATE_PATH", KILL_SWITCH_DEFAULT
            ),
        )
        observed = {
            **snapshot,
            **persisted,
            "live_execution": "BLOCKED",
            "final_execution_authorization": False,
            "capital_plane_mode": "VERIFY_ONLY",
            "capital_authority_granted": False,
            "order_submission_permitted": False,
            "used_otp_session_bootstrap": True,
        }
        source_hash = (
            os.getenv("GITHUB_SHA", "").strip()
            or os.getenv("AURELIA_SOURCE_SHA", "").strip()
            or "LOCAL_UNPINNED"
        )
        config_hash = load_config_hash(ROOT)
        ended = datetime.now(timezone.utc)
        data_hash = sha256(observed)
        evidence = build_evidence(
            evidence_id=f"DERIV_READ_ONLY_STATE:{ended.strftime('%Y%m%dT%H%M%S%fZ')}",
            source_hash=source_hash,
            artifact_hash=sha256({
                "source_hash": source_hash,
                "config_hash": config_hash,
                "data_hash": data_hash,
            }),
            config_hash=config_hash,
            data_hash=data_hash,
            environment="real",
            started_at_utc=now.isoformat(),
            ended_at_utc=ended.isoformat(),
            status="CURRENT",
            valid_until_utc=(ended + timedelta(minutes=30)).isoformat(),
            provenance={
                "origin": "runtime-read-only-verifier",
                "issuer": "AURELIA",
                "source_commit": source_hash,
                "generated_at_utc": ended.isoformat(),
            },
            result="PROVEN",
            invariants_checked=[
                "modern_deriv_otp_authenticated_session",
                "verified_real_account_binding",
                "fresh_balance_before_and_after_snapshot",
                "open_portfolio_read",
                "statement_history_read",
                "statement_balance_chain_reconciled",
                "persistent_daily_risk_state_read_without_mutation",
                "persistent_kill_switch_state_read_without_mutation",
                "live_lock_remains_verify_only",
                "zero_order_submission",
                "zero_capital_movement",
            ],
            invariants_failed=[],
        )
        enriched = dict(evidence)
        enriched["observed"] = observed
        enriched["read_only_scope"] = True
        enriched["orders_submitted"] = 0
        enriched["capital_movement"] = False
        enriched["capital_authority_granted"] = False
        enriched["order_submission_permitted"] = False
        enriched["evidence_class"] = "AUTHENTICATED_READ_ONLY_STATE_VERIFICATION"
        enriched["record_hash"] = payload_sha256(
            {key: value for key, value in enriched.items() if key != "record_hash"}
        )
        write_evidence(OUTPUT, enriched)

        print("DERIV_READONLY_STATE=VERIFIED")
        print(f"DERIV_READONLY_EVIDENCE={OUTPUT}")
        print(f"ACCOUNT={loginid}")
        print(f"BALANCE={snapshot['balance']}")
        print(f"OPEN_POSITIONS={snapshot['open_positions_count']}")
        print(f"STATEMENT_TRANSACTIONS={snapshot['statement_transaction_count']}")
        print(f"DAILY_RISK_STATE_PERSISTED={persisted['daily_risk_state_persisted']}")
        print(f"KILL_SWITCH_STATE_PERSISTED={persisted['kill_switch_state_persisted']}")
        print("ORDERS_SUBMITTED=0")
        print("CAPITAL_MOVEMENT=false")
        return 0
    except ReadOnlyVerificationError as exc:
        print("DERIV_READONLY_STATE=BLOCKED")
        print(f"REASON={str(exc)}")
        return 2
    except Exception as exc:
        print("DERIV_READONLY_STATE=BLOCKED")
        print(f"REASON=VERIFICATION_FAILURE:{type(exc).__name__}")
        return 2
    finally:
        if adapter is not None:
            await adapter.close()


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
