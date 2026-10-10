from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.intraday_bias_cost_model import (
    InstrumentCostProfile,
    LatencyProfile,
    instrument_cost_adjusted_returns,
    instrument_cost_adjusted_statistics,
)
from research.labs.intraday_bias_measurement import ForwardObservation


def make_observation(raw_return: float = 0.01) -> ForwardObservation:
    return ForwardObservation(
        symbol="TEST",
        hour_bucket_utc=10,
        signal_timestamp_utc="2026-10-10T10:00:00Z",
        entry_timestamp_utc="2026-10-10T11:00:00Z",
        exit_timestamp_utc="2026-10-10T12:00:00Z",
        entry_open=100.0,
        exit_open=100.0 * (1.0 + raw_return),
        raw_return=raw_return,
    )


def cost_profile(*, now: datetime | None = None, **changes) -> InstrumentCostProfile:
    observed = (now or datetime.now(timezone.utc)).isoformat()
    values = dict(
        instrument_id="TEST",
        instrument_type="DERIV_SYNTHETIC",
        return_basis="UNDERLYING_PRICE_RETURN",
        spread_cost_bps_round_trip=2.0,
        slippage_cost_bps_round_trip=3.0,
        commission_bps_round_trip=1.0,
        other_fees_bps_round_trip=1.0,
        source="broker-recorded-quote-and-fill-sample",
        observed_at_utc=observed,
        verified=True,
        slippage_excludes_spread=True,
        max_age_seconds=3600.0,
    )
    values.update(changes)
    return InstrumentCostProfile(**values)


def latency_profile(*, now: datetime | None = None, **changes) -> LatencyProfile:
    observed = (now or datetime.now(timezone.utc)).isoformat()
    values = dict(
        p50_ms=50.0,
        p95_ms=100.0,
        p99_ms=250.0,
        sample_count=500,
        source="recorded-request-response-timestamps",
        sensitivity_source="measured-fill-slippage-regression",
        slippage_cost_bps_per_100ms=2.0,
        observed_at_utc=observed,
        max_age_seconds=3600.0,
        minimum_samples=100,
    )
    values.update(changes)
    return LatencyProfile(**values)


class InstrumentCostModelTests(unittest.TestCase):
    def test_round_trip_costs_and_p95_latency_are_deducted_once(self):
        row = make_observation(0.01)
        adjusted = instrument_cost_adjusted_returns(
            [row],
            cost_profile=cost_profile(),
            latency_profile=latency_profile(),
            observation_return_basis="UNDERLYING_PRICE_RETURN",
            latency_scenario="p95",
        )
        # 7 bps instrument costs + 2 bps for 100 ms p95 delay = 9 bps.
        self.assertAlmostEqual(adjusted[0], 0.01 - 9 / 10000)

    def test_unknown_cost_input_blocks_qualification(self):
        with self.assertRaisesRegex(ValueError, "COST_INPUT_UNKNOWN:commission_bps_round_trip"):
            instrument_cost_adjusted_returns(
                [make_observation()],
                cost_profile=cost_profile(commission_bps_round_trip=None),
                latency_profile=latency_profile(),
                observation_return_basis="UNDERLYING_PRICE_RETURN",
            )

    def test_unverified_cost_profile_is_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError, "COST_PROFILE_UNVERIFIED"):
            instrument_cost_adjusted_returns(
                [make_observation()],
                cost_profile=cost_profile(verified=False),
                latency_profile=latency_profile(),
                observation_return_basis="UNDERLYING_PRICE_RETURN",
            )

    def test_stale_cost_profile_is_rejected(self):
        stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
        with self.assertRaisesRegex(ValueError, "COST_PROFILE_STALE"):
            instrument_cost_adjusted_returns(
                [make_observation()],
                cost_profile=cost_profile(now=stale_time),
                latency_profile=latency_profile(),
                observation_return_basis="UNDERLYING_PRICE_RETURN",
            )

    def test_unknown_return_basis_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "RETURN_BASIS_MISMATCH"):
            instrument_cost_adjusted_returns(
                [make_observation()],
                cost_profile=cost_profile(return_basis="CONTRACT_PNL_RETURN"),
                latency_profile=latency_profile(),
                observation_return_basis="UNDERLYING_PRICE_RETURN",
            )

    def test_slippage_must_be_separate_from_spread(self):
        with self.assertRaisesRegex(ValueError, "SLIPPAGE_MAY_DOUBLE_COUNT_SPREAD"):
            instrument_cost_adjusted_returns(
                [make_observation()],
                cost_profile=cost_profile(slippage_excludes_spread=False),
                latency_profile=latency_profile(),
                observation_return_basis="UNDERLYING_PRICE_RETURN",
            )

    def test_latency_quantiles_must_be_monotonic(self):
        profile = latency_profile(p50_ms=120.0, p95_ms=100.0, p99_ms=250.0)
        self.assertIn("LATENCY_QUANTILES_NOT_MONOTONIC", profile.validate())

    def test_latency_requires_enough_samples_and_cost_sensitivity(self):
        profile = latency_profile(sample_count=20, slippage_cost_bps_per_100ms=None)
        errors = profile.validate()
        self.assertIn("LATENCY_SAMPLE_COUNT_INSUFFICIENT", errors)
        self.assertIn("LATENCY_COST_SENSITIVITY_UNKNOWN", errors)

    def test_latency_scenario_rejects_unknown_quantile(self):
        with self.assertRaisesRegex(ValueError, "LATENCY_SCENARIO_MUST_BE_P50_P95_OR_P99"):
            latency_profile().scenario_delay_ms("p90")

    def test_statistics_report_net_outcomes(self):
        rows = [make_observation(0.01), make_observation(-0.005)]
        stats = instrument_cost_adjusted_statistics(
            rows,
            cost_profile=cost_profile(),
            latency_profile=latency_profile(),
            observation_return_basis="UNDERLYING_PRICE_RETURN",
            latency_scenario="p50",
        )
        self.assertEqual(stats.n, 2)
        self.assertAlmostEqual(stats.expectancy, (0.01 - 8 / 10000 + (-0.005 - 8 / 10000)) / 2)


if __name__ == "__main__":
    unittest.main()
