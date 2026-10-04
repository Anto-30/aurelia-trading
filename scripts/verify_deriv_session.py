from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence
from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager, DerivSessionManagerError
from runtime.core.events import canonical_json, sha256
from runtime.core.models import CapitalSnapshot
from runtime.core.runtime_config import load_config_hash


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.getenv("DERIV_EVIDENCE_OUT", "artifacts/deriv_authenticated_session.json"))


async def run() -> int:
    started = datetime.now(timezone.utc)
    # Accept the canonical AURELIA names plus the operator-facing aliases
    # used by the protected deployment environment. Values are never logged.
    token = os.getenv("DERIV_AUTH_TOKEN") or os.getenv("DERIV_PAT", "")
    app_id = os.getenv("DERIV_APP_ID", "")
    expected_loginid = os.getenv("DERIV_EXPECTED_LOGINID") or os.getenv(
        "DERIV_AUTHORIZED_ACCOUNT_ID", ""
    )
    expected_currency = os.getenv("DERIV_EXPECTED_CURRENCY", "USD")
    expected_environment = os.getenv("DERIV_ENVIRONMENT", "real").lower()
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()
    source_hash = os.getenv("GITHUB_SHA", "LOCAL_UNPINNED")

    if auth_mode not in {"pat", "oauth"}:
        print("DERIV_AUTH_SESSION=BLOCKED")
        print("DERIV_AUTH_SESSION_REASON=UNSUPPORTED_AUTH_MODE")
        return 3
    if auth_mode == "pat" and not app_id:
        print("DERIV_AUTH_SESSION=NOT_CONFIGURED")
        print("DERIV_AUTH_SESSION_REASON=DERIV_APP_ID_MISSING_FOR_PAT")
        return 2

    if not token:
        print("DERIV_AUTH_SESSION=NOT_CONFIGURED")
        return 2
    if not expected_loginid:
        print("DERIV_AUTH_SESSION=NOT_CONFIGURED")
        print("DERIV_AUTH_SESSION_REASON=EXPECTED_LOGINID_MISSING")
        return 2
    if expected_environment not in {"real", "demo"}:
        print("DERIV_AUTH_SESSION=BLOCKED")
        print("DERIV_AUTH_SESSION_REASON=UNSUPPORTED_ENVIRONMENT")
        return 3

    manager = DerivSessionManager(
        expected_loginid=expected_loginid,
        expected_environment=expected_environment,
        expected_currency=expected_currency,
    )
    adapter: DerivAdapter | None = None

    try:
        bootstrap = manager.bootstrap(
            bearer_token=token,
            app_id=app_id,
        )
        binding = bootstrap.binding
        if binding.loginid != expected_loginid:
            raise RuntimeError("ACCOUNT_LOGINID_MISMATCH")
        if binding.environment != expected_environment:
            raise RuntimeError("ACCOUNT_ENVIRONMENT_MISMATCH")
        if binding.currency != expected_currency:
            raise RuntimeError("ACCOUNT_CURRENCY_MISMATCH")

        adapter = DerivAdapter(
            ws_url=bootstrap.websocket.url,
            expected_loginid=expected_loginid,
            expected_currency=expected_currency,
            environment=expected_environment,
        )
        account = await adapter.connect()
        snapshot: CapitalSnapshot = await adapter.get_balance()

        if account.loginid != expected_loginid:
            raise RuntimeError("CONNECTED_ACCOUNT_IDENTITY_MISMATCH")
        if account.environment != expected_environment:
            raise RuntimeError("CONNECTED_ACCOUNT_ENVIRONMENT_MISMATCH")
        expected_account_type = "real" if expected_environment == "real" else "demo"
        if account.account_type != expected_account_type:
            raise RuntimeError("CONNECTED_ACCOUNT_TYPE_MISMATCH")
        if not snapshot.is_valid():
            raise RuntimeError("CAPITAL_SNAPSHOT_INVALID")

        ended = datetime.now(timezone.utc)
        observed = {
            "account_loginid": snapshot.account.loginid,
            "account_type": snapshot.account.account_type,
            "environment": snapshot.account.environment,
            "currency": snapshot.currency,
            "balance": snapshot.balance,
            "available_balance": snapshot.available_balance,
            "captured_at_utc": snapshot.captured_at.isoformat(),
            "authenticated_ws_endpoint": bootstrap.safe_websocket_url,
        }
        data_hash = hashlib.sha256(
            canonical_json(observed).encode("utf-8")
        ).hexdigest()
        artifact_hash = sha256(
            {
                "source_hash": source_hash,
                "config_hash": load_config_hash(ROOT),
                "data_hash": data_hash,
                "authenticated_ws_endpoint": bootstrap.safe_websocket_url,
            }
        )
        record = build_evidence(
            evidence_id=f"DERIV_AUTH_SESSION:{ended.strftime('%Y%m%dT%H%M%SZ')}",
            source_hash=source_hash,
            artifact_hash=artifact_hash,
            config_hash=load_config_hash(ROOT),
            data_hash=data_hash,
            environment="ci",
            started_at_utc=started.isoformat(),
            ended_at_utc=ended.isoformat(),
            status="CURRENT",
            valid_until_utc=(ended + timedelta(minutes=5)).isoformat(),
            provenance={
                "origin": "ci",
                "issuer": f"github-actions:{os.getenv('GITHUB_RUN_ID', 'LOCAL')}",
                "source_commit": source_hash,
                "generated_at_utc": ended.isoformat(),
            },
            result="PROVEN",
            invariants_checked=[
                f"exact_{expected_environment}_account_binding",
                "authenticated_websocket_environment",
                f"auth_mode_{auth_mode}",
                "account_identity_match",
                "currency_match",
                "fresh_balance_snapshot",
                "no_order_submission",
                "capital_authority_not_granted",
            ],
            invariants_failed=[],
        )
        enriched = dict(record)
        enriched["observed"] = observed
        enriched["orders_submitted"] = 0
        enriched["capital_authority_granted"] = False
        enriched["verification_scope"] = f"AUTHENTICATED_DERIV_{expected_environment.upper()}_SESSION"
        enriched["order_submission_permitted"] = False
        enriched["record_hash"] = payload_sha256(
            {key: value for key, value in enriched.items() if key != "record_hash"}
        )
        write_evidence(OUTPUT, enriched)

        print("DERIV_AUTH_SESSION=VERIFIED")
        print(f"DERIV_ACCOUNT_LOGINID={snapshot.account.loginid}")
        print(f"DERIV_ACCOUNT_ENVIRONMENT={snapshot.account.environment}")
        print(f"DERIV_VERIFICATION_SCOPE=AUTHENTICATED_DERIV_{expected_environment.upper()}_SESSION")
        print(f"DERIV_ACCOUNT_CURRENCY={snapshot.currency}")
        print("DERIV_BALANCE_VERIFIED=true")
        print("DERIV_ORDERS_SUBMITTED=0")
        print("DERIV_CAPITAL_AUTHORITY_GRANTED=false")
        print(f"DERIV_EVIDENCE_PATH={OUTPUT}")
        print(f"DERIV_EVIDENCE_HASH={enriched['record_hash']}")
        return 0
    except Exception as exc:
        print("DERIV_AUTH_SESSION=FAILED")
        print(f"DERIV_AUTH_SESSION_REASON={type(exc).__name__}")
        return 1
    finally:
        if adapter is not None:
            await adapter.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
