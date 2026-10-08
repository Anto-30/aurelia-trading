from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence
from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager
from runtime.core.events import sha256
from runtime.core.runtime_config import load_config_hash
from runtime.core.secrets import get_optional_secret


OUTPUT = Path(
    os.getenv(
        "DERIV_BROKER_EVIDENCE_OUT",
        "artifacts/deriv_broker_account_evidence.json",
    )
)


def fail(reason: str) -> int:
    print("DERIV_BROKER_EVIDENCE=FAILED")
    print(f"REASON={reason}")
    return 2


def _safe_transaction(row: dict) -> dict:
    # Preserve broker-verifiable identifiers and economics while avoiding
    # unnecessary free-form descriptions in the evidence artifact.
    keys = (
        "transaction_id",
        "id",
        "action_type",
        "amount",
        "balance",
        "currency",
        "timestamp",
        "date",
        "contract_id",
        "contract_type",
        "symbol",
        "underlying_symbol",
    )
    return {key: row[key] for key in keys if key in row}


async def run() -> int:
    token = get_optional_secret("DERIV_AUTH_TOKEN") or get_optional_secret("DERIV_PAT")
    app_id = get_optional_secret("DERIV_APP_ID")
    expected_loginid = (
        os.getenv("DERIV_EXPECTED_LOGINID")
        or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID")
        or ""
    )
    expected_currency = os.getenv("DERIV_EXPECTED_CURRENCY", "USD")
    environment = os.getenv("DERIV_ENVIRONMENT", "real").strip().lower()
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()
    source_hash = os.getenv("GITHUB_SHA", "LOCAL_UNPINNED")

    if not token:
        return fail("AUTH_TOKEN_MISSING")
    if not expected_loginid:
        return fail("EXPECTED_ACCOUNT_BINDING_MISSING")
    if environment != "real":
        return fail("REAL_ACCOUNT_REQUIRED")
    if auth_mode not in {"pat", "oauth"}:
        return fail("UNSUPPORTED_AUTH_MODE")
    if auth_mode == "pat" and not app_id:
        return fail("DERIV_APP_ID_REQUIRED_FOR_PAT")

    adapter: DerivAdapter | None = None
    started = datetime.now(timezone.utc)

    try:
        manager = DerivSessionManager(
            expected_loginid=expected_loginid,
            expected_environment="real",
            expected_currency=expected_currency,
        )
        bootstrap = manager.bootstrap(
            bearer_token=token,
            app_id=app_id,
        )
        if bootstrap.binding.loginid != expected_loginid:
            return fail("ACCOUNT_BINDING_MISMATCH")

        adapter = DerivAdapter(
            ws_url=bootstrap.websocket.url,
            expected_loginid=expected_loginid,
            expected_currency=expected_currency,
            environment="real",
        )
        account = await adapter.connect()
        if account.loginid != expected_loginid or account.account_type != "real":
            return fail("CONNECTED_ACCOUNT_BINDING_MISMATCH")
        if account.currency != expected_currency:
            return fail("CONNECTED_CURRENCY_MISMATCH")

        balance = await adapter.get_balance()
        statement = await adapter.statement(limit=999, action_type="buy")
        portfolio = await adapter.portfolio()

        buy_rows = [_safe_transaction(row) for row in statement]
        buy_ids = [
            str(row.get("transaction_id") or row.get("id") or "")
            for row in buy_rows
            if str(row.get("transaction_id") or row.get("id") or "")
        ]
        open_contract_ids = [
            str(row.get("contract_id") or row.get("id") or "")
            for row in portfolio
            if str(row.get("contract_id") or row.get("id") or "")
        ]

        observed = {
            "account_loginid": account.loginid,
            "account_type": account.account_type,
            "environment": account.environment,
            "currency": balance.currency,
            "available_balance": balance.available_balance,
            "balance_captured_at_utc": balance.captured_at.isoformat(),
            "statement_action_type": "buy",
            "broker_buy_transaction_count": len(buy_ids),
            "broker_buy_transaction_ids": buy_ids,
            "open_contract_count": len(open_contract_ids),
            "open_contract_ids": open_contract_ids,
            "statement_transactions": buy_rows,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "capital_movement_performed_by_verifier": False,
            "capital_authority_granted_by_verifier": False,
            "trade_attribution": "BROKER_ACCOUNT_LEVEL_UNATTRIBUTED",
        }

        data_hash = sha256(observed)
        ended = datetime.now(timezone.utc)
        record = build_evidence(
            evidence_id=f"DERIV_BROKER_ACCOUNT:{ended.strftime('%Y%m%dT%H%M%SZ')}",
            source_hash=source_hash,
            artifact_hash=sha256(
                {
                    "data_hash": data_hash,
                    "config_hash": load_config_hash(ROOT),
                }
            ),
            config_hash=load_config_hash(ROOT),
            data_hash=data_hash,
            environment="production",
            started_at_utc=started.isoformat(),
            ended_at_utc=ended.isoformat(),
            status="CURRENT",
            valid_until_utc=(ended + timedelta(minutes=5)).isoformat(),
            provenance={
                "origin": "runtime",
                "issuer": "aurelia-deriv-broker-evidence-verifier",
                "source_commit": source_hash,
                "generated_at_utc": ended.isoformat(),
                "deployment_id": os.getenv(
                    "AURELIA_DEPLOYMENT_ID",
                    "DERIV-BROKER-EVIDENCE",
                ),
            },
            result="PROVEN",
            invariants_checked=[
                "real_account_binding",
                "fresh_authenticated_balance",
                "authenticated_statement_read",
                "buy_transaction_inventory",
                "authenticated_portfolio_read",
                "no_order_submission",
                "no_capital_authority_grant",
                "broker_account_level_attribution_only",
            ],
            invariants_failed=[],
        )
        enriched = dict(record)
        enriched["observed"] = observed
        enriched["orders_submitted"] = 0
        enriched["capital_authority_granted"] = False
        enriched["verification_scope"] = "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY"
        enriched["order_submission_permitted"] = False
        enriched["record_hash"] = payload_sha256(
            {
                key: value for key, value in enriched.items()
                if key != "record_hash"
            }
        )
        write_evidence(OUTPUT, enriched)

        print("DERIV_BROKER_EVIDENCE=PROVEN")
        print(f"DERIV_ACCOUNT={account.loginid}")
        print(f"BROKER_BUY_TRANSACTION_COUNT={len(buy_ids)}")
        print(f"OPEN_CONTRACT_COUNT={len(open_contract_ids)}")
        print("ORDERS_SUBMITTED=0")
        print("CAPITAL_AUTHORITY=false")
        print(f"DERIV_EVIDENCE_PATH={OUTPUT}")
        print(f"DERIV_EVIDENCE_HASH={enriched['record_hash']}")
        return 0
    except Exception as exc:
        print("DERIV_BROKER_EVIDENCE=FAILED")
        print(f"REASON={type(exc).__name__}")
        return 1
    finally:
        if adapter is not None:
            await adapter.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
