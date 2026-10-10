from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.intraday_bias_cost_model import (
    ApiRateLimitSimulator,
    DerivRateLimitProfile,
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

class DerivRateLimitSimulatorTests(unittest.TestCase):
    def test_websocket_trading_calls_share_one_budget(self):
        profile = DerivRateLimitProfile(ws_trading_per_minute=2, ws_trading_per_hour=10)
        sim = ApiRateLimitSimulator(profile)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="proposal", timestamp_seconds=0).allowed)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="buy", timestamp_seconds=1).allowed)
        limited = sim.simulate_request(protocol="ws", request_type="sell", timestamp_seconds=2)
        self.assertFalse(limited.allowed)
        self.assertEqual(limited.reason, "RATE_LIMITED")
        self.assertGreater(limited.retry_after_seconds, 0)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="sell", timestamp_seconds=60).allowed)

    def test_websocket_hourly_budget_is_separate_from_minute_budget(self):
        profile = DerivRateLimitProfile(ws_other_per_minute=10, ws_other_per_hour=2)
        sim = ApiRateLimitSimulator(profile)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="authorize", timestamp_seconds=0).allowed)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="authorize", timestamp_seconds=1).allowed)
        self.assertFalse(sim.simulate_request(protocol="ws", request_type="authorize", timestamp_seconds=2).allowed)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="authorize", timestamp_seconds=3600).allowed)

    def test_ping_budget_is_per_connection(self):
        sim = ApiRateLimitSimulator(DerivRateLimitProfile(ws_ping_per_second=2))
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=0, connection_key="A").allowed)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=0.1, connection_key="A").allowed)
        self.assertFalse(sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=0.2, connection_key="A").allowed)
        self.assertTrue(sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=0.2, connection_key="B").allowed)

    def test_rest_limits_are_applied_to_ip_and_account(self):
        profile = DerivRateLimitProfile(rest_ip_per_minute=10, rest_ip_per_10_minutes=20, rest_account_per_minute=2)
        sim = ApiRateLimitSimulator(profile)
        self.assertTrue(sim.simulate_request(protocol="rest", request_type="GET", timestamp_seconds=0, account_key="A", ip_key="X").allowed)
        self.assertTrue(sim.simulate_request(protocol="rest", request_type="GET", timestamp_seconds=1, account_key="A", ip_key="Y").allowed)
        denied = sim.simulate_request(protocol="rest", request_type="POST", timestamp_seconds=2, account_key="A", ip_key="Z")
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.budget, "rest")

    def test_time_regression_and_unknown_protocol_are_rejected(self):
        sim = ApiRateLimitSimulator()
        sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=2)
        with self.assertRaisesRegex(ValueError, "RATE_LIMIT_TIMESTAMP_MUST_BE_MONOTONIC"):
            sim.simulate_request(protocol="ws", request_type="ping", timestamp_seconds=1)
        with self.assertRaisesRegex(ValueError, "RATE_LIMIT_PROTOCOL_MUST_BE_WEBSOCKET_OR_REST"):
            ApiRateLimitSimulator().simulate_request(protocol="tcp", request_type="other", timestamp_seconds=0)

