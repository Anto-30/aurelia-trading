#!/usr/bin/env python3
"""Capture Deriv R_100 market/contract metadata without inventing economics.

Deriv's current public market-data API documents active_symbols and contracts_for on
the WebSocket v3 interface. This script does NOT call an undocumented REST route and
does not submit orders. Public market metadata does not itself prove a tradeable
Multiplier contract's cash-per-price-unit, fill spread, slippage, or tick increment.
Those fields remain null until supported by exact, independently anchored evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.atos_validation.deriv_data import DerivHistoryClient

SCHEMA = "aurelia.instrument_specs_capture.v1"
DOCS = {
    "active_symbols": "https://developers.deriv.com/docs/data/active-symbols/",
    "contracts_for": "https://developers.deriv.com/docs/data/contracts-for/",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def fetch_metadata(client: DerivHistoryClient, symbol: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Fetch raw public market metadata; no account authorization or trading request."""
    active_response = client.request_message(
        {"active_symbols": "brief", "req_id": 101},
        expected_msg_type="active_symbols",
    )
    contracts_response = client.request_message(
        {"contracts_for": symbol, "req_id": 102},
        expected_msg_type="contracts_for",
    )
    active_symbols = active_response.get("active_symbols")
    if not isinstance(active_symbols, list):
        raise ValueError("Deriv active_symbols response did not contain a list")
    matches = [item for item in active_symbols if isinstance(item, dict) and item.get("symbol") == symbol]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one active_symbols entry for {symbol}, found {len(matches)}")
    contracts = contracts_response.get("contracts_for")
    if not isinstance(contracts, dict):
        raise ValueError("Deriv contracts_for response is missing its expected object")
    available = contracts.get("available")
    if not isinstance(available, list):
        raise ValueError("Deriv contracts_for response is missing the available-contract list")
    hashes = {
        "active_symbols_response_sha256": sha256_bytes(canonical_json(active_response)),
        "contracts_for_response_sha256": sha256_bytes(canonical_json(contracts_response)),
    }
    return matches[0], contracts, hashes


def build_spec_document(
    *,
    symbol: str,
    active_symbol: dict[str, Any],
    contracts: dict[str, Any],
    response_hashes: dict[str, str],
    endpoint: str,
    app_id_used: str | None,
) -> dict[str, Any]:
    """Capture source fields verbatim and intentionally leave unsupported economics null."""
    available = contracts.get("available", [])
    contract_types = sorted({
        str(item["contract_type"])
        for item in available
        if isinstance(item, dict) and isinstance(item.get("contract_type"), str)
    })
    # pip/pip_size is display precision, not proof of a minimum tradable tick increment.
    # contracts_for lists product types and restrictions, not multiplier payoff/cash value.
    missing_fields = {
        "tick_size": "NOT_PROVIDED_AS_EXECUTABLE_TICK_INCREMENT_BY_CAPTURED_PUBLIC_ENDPOINTS",
        "contract_multiplier": "NO_VERIFIED_LINEAR_CASH_MULTIPLIER_FOR_A_SPECIFIED_PRODUCT",
        "spread_pips": "NO_OBSERVED_BID_ASK_SPREAD_IN_ACTIVE_SYMBOLS_OR_CONTRACTS_FOR",
        "slippage_bps": "REQUIRES_OBSERVED_EXECUTION_OR_EXPLICIT_UNVERIFIED_SCENARIO",
        "cash_per_price_unit_per_unit": "CONTRACT_PAYOFF_OR_SPECIFIC_PRODUCT_CASH_CONVERSION_NOT_PROVIDED",
    }
    return {
        "schema": SCHEMA,
        "symbol": symbol,
        "captured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "api_type": "PUBLIC_WEBSOCKET_MARKET_DATA",
            "endpoint_host": endpoint,
            "app_id_used": app_id_used or None,
            "authentication_used": False,
            "trading_requests_sent": False,
            "documentation": DOCS,
            "response_sha256": response_hashes,
        },
        "active_symbol_metadata": active_symbol,
        "contracts_for_metadata": contracts,
        "available_contract_types": contract_types,
        "execution_product": None,
        "specifications": {
            "tick_size": None,
            "contract_multiplier": None,
            "cash_per_price_unit_per_unit": None,
            "spread_pips": None,
            "slippage_bps": None,
            "commission_cash_per_unit_round_trip": None,
        },
        "field_status": missing_fields,
        "capture_status": "METADATA_CAPTURED_ECONOMICS_INCOMPLETE",
        "simulator_ready": False,
        "qualification_note": (
            "The captured market metadata identifies the symbol and available contract types only. "
            "It does not verify instrument tick size, linear contract multiplier, bid/ask spread, "
            "slippage, commission, or the product's payoff. Do not use this file as a verified "
            "economic configuration until those inputs are independently sourced, hash-anchored, "
            "and tied to one explicitly selected Deriv contract/product."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="R_100")
    parser.add_argument("--app-id", default=None, help="Optional legacy/public app identifier; not an account token")
    parser.add_argument("--out", type=Path, default=Path("config/instrument_specs.json"))
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--retry-base-seconds", type=float, default=1.5)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.symbol or len(args.symbol) > 30 or not args.symbol.replace("_", "").isalnum():
        parser.error("--symbol must be a valid short Deriv symbol")
    if args.out.exists() and not args.overwrite:
        print(f"INSTRUMENT_SPECS=BLOCKED\nREASON=refusing to overwrite existing file: {args.out}")
        return 2
    try:
        client = DerivHistoryClient(
            app_id=args.app_id,
            max_attempts=args.max_attempts,
            retry_base_seconds=args.retry_base_seconds,
        )
        active, contracts, hashes = fetch_metadata(client, args.symbol)
        doc = build_spec_document(
            symbol=args.symbol,
            active_symbol=active,
            contracts=contracts,
            response_hashes=hashes,
            endpoint=client.last_connected_url.split("?")[0] if getattr(client, "last_connected_url", None) else "documented public v3 endpoint",
            app_id_used=client.app_id,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        temp = args.out.with_name(args.out.name + ".tmp")
        temp.write_text(encoded, encoding="utf-8")
        os.replace(temp, args.out)
        print("INSTRUMENT_SPECS=CAPTURED_INCOMPLETE")
        print(f"SPEC_CAPTURE_SHA256={sha256_bytes(args.out.read_bytes())}")
        print(f"ACTIVE_SYMBOL_RESPONSE_SHA256={hashes['active_symbols_response_sha256']}")
        print(f"CONTRACTS_FOR_RESPONSE_SHA256={hashes['contracts_for_response_sha256']}")
        print(f"AVAILABLE_CONTRACT_TYPES={','.join(doc['available_contract_types']) or 'none_reported'}")
        print(f"SPEC_PATH={args.out}")
        print("TICK_SIZE_VERIFIED=false")
        print("CONTRACT_MULTIPLIER_VERIFIED=false")
        print("SPREAD_VERIFIED=false")
        print("SIMULATOR_READY=false")
        return 3
    except Exception as exc:
        print("INSTRUMENT_SPECS=FAILED")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
