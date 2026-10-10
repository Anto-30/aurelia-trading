from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from research.labs.instrument_specification import (
    InstrumentSpecification,
    InstrumentSpecificationRegistry,
)


UTC = timezone.utc
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def verified_deriv_contract(**changes):
    values = dict(
        instrument_id="R_100",
        category="DERIV_FIXED_PAYOUT",
        specification_version="test-v1",
        provider="Deriv",
        account_type="real",
        source_uri="https://example.invalid/verified-account-product-spec",
        verified=True,
        observed_at_utc=NOW.isoformat(),
        price_precision=2,
        tick_size_applicable=True,
        tick_size=0.01,
        minimum_stake_or_order_size=1.0,
        size_increment=0.01,
        contract_multiplier=1.0,
        payoff_model="PURCHASED_CONTRACT_MAX_LOSS_EQUALS_STAKE",
        trading_hours="24x7 broker-defined synthetic session",
        trading_hours_timezone="UTC",
        settlement_rules="broker terminal contract status and payout",
        supported_order_types=("proposal", "buy", "sell"),
        order_book_model=False,
        spread_model="quoted_proposal_price",
        slippage_model="measure proposal-to-buy timing and pricing separately",
        commission_model="no separate commission unless recorded by broker",
        financing_model="not applicable to this short-duration purchased-contract example",
        native_stop_supported=False,
        native_oco_supported=False,
        partial_fills_supported=False,
        maker_fee_bps=None,
        taker_fee_bps=None,
        maximum_age_seconds=3600.0,
    )
    values.update(changes)
    return InstrumentSpecification(**values)


class InstrumentSpecificationTests(unittest.TestCase):
    def test_complete_versioned_spec_can_qualify(self):
        spec = verified_deriv_contract()
        self.assertTrue(spec.qualifies(now=NOW))
        self.assertEqual(spec.qualification_report(now=NOW)["status"], "PASS")

    def test_unknown_minimum_or_contract_economics_blocks_qualification(self):
        spec = verified_deriv_contract(minimum_stake_or_order_size=None, payoff_model=None)
        errors = spec.validation_errors(now=NOW)
        self.assertIn("MINIMUM_STAKE_OR_ORDER_SIZE_UNKNOWN_OR_INVALID", errors)
        self.assertIn("PAYOFF_MODEL_UNKNOWN", errors)

    def test_stale_or_unverified_spec_blocks_qualification(self):
        stale = verified_deriv_contract(
            observed_at_utc=(NOW - timedelta(hours=2)).isoformat()
        )
        self.assertIn("INSTRUMENT_SPECIFICATION_STALE", stale.validation_errors(now=NOW))
        unverified = verified_deriv_contract(verified=False)
        self.assertIn("INSTRUMENT_SPECIFICATION_UNVERIFIED", unverified.validation_errors(now=NOW))

    def test_maker_taker_fees_are_not_applied_to_non_order_book_contract(self):
        spec = verified_deriv_contract(maker_fee_bps=1.0, taker_fee_bps=2.0)
        self.assertIn(
            "MAKER_TAKER_FEES_NOT_APPLICABLE_TO_THIS_MODEL",
            spec.validation_errors(now=NOW),
        )

    def test_order_book_spec_requires_explicit_maker_and_taker_fees(self):
        spec = verified_deriv_contract(
            category="EXCHANGE_TRADED",
            order_book_model=True,
            maker_fee_bps=None,
            taker_fee_bps=None,
        )
        errors = spec.validation_errors(now=NOW)
        self.assertIn("ORDER_BOOK_MAKER_FEE_UNKNOWN_OR_INVALID", errors)
        self.assertIn("ORDER_BOOK_TAKER_FEE_UNKNOWN_OR_INVALID", errors)

    def test_registry_does_not_infer_unregistered_instruments(self):
        registry = InstrumentSpecificationRegistry({"R_100": verified_deriv_contract()})
        result = registry.qualify("UNKNOWN")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("INSTRUMENT_SPECIFICATION_NOT_REGISTERED", result["reasons"])
        self.assertFalse(replace(verified_deriv_contract(), verified=False).qualifies(now=NOW))


if __name__ == "__main__":
    unittest.main()
