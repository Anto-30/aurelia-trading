from __future__ import annotations

import unittest
import warnings
from datetime import datetime, timezone

from research.labs.deterministic_intraday_strategies import StrategyCandidate
from research.labs.dual_asset_session_volatility import (
    VolatilitySizer,
    VolatilitySizingConfig,
    apply_session_filter,
    classify_session,
    evaluate_research_entry_controls,
    is_kill_zone,
    prepare_candidate_for_research_simulation,
    select_volatility_estimator_from_dsr,
    test_c_session_edge,
)


class FakeFrame:
    def __init__(self, values=None, index=None):
        self.values = dict(values or {})
        self.index = list(index or [])

    def copy(self):
        return FakeFrame(self.values, self.index)

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = list(value)


class DualAssetSessionTests(unittest.TestCase):
    def test_london_window_converts_with_uk_dst(self):
        winter_utc = datetime(2026, 1, 15, 7, 30, tzinfo=timezone.utc)
        summer_utc = datetime(2026, 7, 15, 6, 30, tzinfo=timezone.utc)
        self.assertEqual(classify_session(winter_utc, "financial"), "LONDON")
        self.assertEqual(classify_session(summer_utc, "financial"), "LONDON")

    def test_ny_am_window_converts_with_us_dst(self):
        winter_utc = datetime(2026, 1, 15, 13, 30, tzinfo=timezone.utc)
        summer_utc = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(classify_session(winter_utc, "financial"), "NY_AM")
        self.assertEqual(classify_session(summer_utc, "financial"), "NY_AM")

    def test_london_precedes_asian_in_overlap(self):
        # 06:30 UTC in July is 07:30 London and 15:30 Tokyo.
        timestamp = datetime(2026, 7, 15, 6, 30, tzinfo=timezone.utc)
        self.assertEqual(classify_session(timestamp, "financial"), "LONDON")

    def test_asian_and_dead_windows(self):
        asian = datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
        dead = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        self.assertEqual(classify_session(asian, "financial"), "ASIAN")
        self.assertEqual(classify_session(dead, "financial"), "DEAD")

    def test_naive_timestamps_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            classify_session(datetime(2026, 1, 15, 7, 30), "financial")

    def test_dataframe_annotation_is_copy_and_synthetic_bypass_is_logged(self):
        frame = FakeFrame({"close": [100.0, 101.0]}, index=[0, 1])
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            output = apply_session_filter(frame, "synthetic")
        self.assertEqual(output.values["session_label"], ["SYNTHETIC_BYPASS"] * 2)
        self.assertNotIn("session_label", frame.values)
        self.assertTrue(any("bypassed" in str(item.message).lower() for item in recorded))

    def test_financial_dataframe_gets_dst_aware_labels(self):
        frame = FakeFrame(
            {"timestamp_utc": [
                "2026-01-15T07:30:00Z",
                "2026-01-15T13:30:00Z",
                "2026-01-15T10:30:00Z",
            ]},
            index=[0, 1, 2],
        )
        result = apply_session_filter(frame, "financial", timestamp_column="timestamp_utc")
        self.assertEqual(result.values["session_label"], ["LONDON", "NY_AM", "DEAD"])
        self.assertNotIn("session_label", frame.values)

    def test_synthetic_kill_zone_mask_is_all_true_and_warns(self):
        frame = FakeFrame(index=[0, 1, 2])
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            mask = is_kill_zone(frame, "LONDON", asset_class="synthetic")
        self.assertEqual(list(mask), [True, True, True])
        self.assertTrue(recorded)

    def test_financial_kill_zone_buffer_expands_local_window(self):
        frame = FakeFrame(
            {"timestamp_utc": [
                "2026-01-15T06:50:00Z",
                "2026-01-15T07:30:00Z",
                "2026-01-15T10:20:00Z",
            ]},
            index=[0, 1, 2],
        )
        mask = is_kill_zone(
            frame, "LONDON", buffer_minutes=15,
            asset_class="financial", timestamp_column="timestamp_utc",
        )
        self.assertEqual(list(mask), [True, True, False])


class VolatilitySizerTests(unittest.TestCase):
    def _config(self, **overrides):
        values = {
            "periods_per_year": 1,
            "target_vol_annual": 0.01,
            "window": 20,
            "estimator": "rolling",
            "min_multiplier": 0.1,
            "max_multiplier": 3.0,
            "max_risk_pct": 0.02,
        }
        values.update(overrides)
        return VolatilitySizingConfig(**values)

    def test_schedule_uses_only_returns_before_current_trade_bar(self):
        returns_a = [0.01 if i % 2 == 0 else -0.01 for i in range(25)]
        returns_b = list(returns_a)
        returns_b[20] = 0.50  # return at bar 20 cannot size a trade at bar 20
        sizer = VolatilitySizer(self._config())
        point_a = sizer.build_schedule(returns_a)[20]
        point_b = sizer.build_schedule(returns_b)[20]
        self.assertTrue(point_a.ready)
        self.assertAlmostEqual(point_a.realized_vol_annualized, point_b.realized_vol_annualized)

    def test_doubling_realized_volatility_halves_inverse_vol_multiplier(self):
        base = [0.01 if i % 2 == 0 else -0.01 for i in range(25)]
        doubled = [2.0 * value for value in base]
        sizer = VolatilitySizer(self._config())
        m1 = sizer.build_schedule(base, base_risk_pct=0.005)[20].bounded_multiplier
        m2 = sizer.build_schedule(doubled, base_risk_pct=0.005)[20].bounded_multiplier
        self.assertAlmostEqual(m2, m1 / 2.0, places=6)

    def test_warmup_never_falls_back_to_base_risk(self):
        sizer = VolatilitySizer(self._config())
        schedule = sizer.build_schedule([0.01, -0.01] * 5)
        self.assertTrue(all(not point.ready for point in schedule))
        self.assertTrue(all(point.effective_risk_pct is None for point in schedule))

    def test_multiplier_and_absolute_layer6_risk_are_bounded(self):
        sizer = VolatilitySizer(self._config(target_vol_annual=1.0))
        returns = [0.0001 if i % 2 == 0 else -0.0001 for i in range(25)]
        point = sizer.build_schedule(returns, base_risk_pct=0.01)[20]
        self.assertEqual(point.bounded_multiplier, 3.0)
        self.assertEqual(point.effective_risk_pct, 0.02)
        self.assertLessEqual(point.effective_risk_pct, 0.02)

    def test_config_cannot_weaken_absolute_multiplier_bounds(self):
        with self.assertRaisesRegex(ValueError, "VOLATILITY_MAX_MULTIPLIER_OUTSIDE_HARD_BOUNDS"):
            self._config(max_multiplier=3.01)
        with self.assertRaisesRegex(ValueError, "VOLATILITY_MIN_MULTIPLIER_OUTSIDE_HARD_BOUNDS"):
            self._config(min_multiplier=0.09)
        with self.assertRaisesRegex(ValueError, "VOLATILITY_MIN_MULTIPLIER_OUTSIDE_HARD_BOUNDS"):
            self._config(min_multiplier=1.01)

    def test_lower_multiplier_floor_is_applied(self):
        sizer = VolatilitySizer(self._config(target_vol_annual=0.001))
        returns = [0.02 if i % 2 == 0 else -0.02 for i in range(25)]
        point = sizer.build_schedule(returns)[20]
        self.assertEqual(point.bounded_multiplier, 0.1)

    def test_ewma_reacts_more_to_a_recent_volatility_shock(self):
        returns = [0.001] * 20 + [0.10] + [0.001] * 3
        rolling = VolatilitySizer(self._config(estimator="rolling"))
        ewma = VolatilitySizer(self._config(estimator="ewma", ewma_lambda=0.90))
        rolling_point = rolling.build_schedule(returns)[21]
        ewma_point = ewma.build_schedule(returns)[21]
        self.assertTrue(rolling_point.ready and ewma_point.ready)
        self.assertGreater(ewma_point.realized_vol_annualized, rolling_point.realized_vol_annualized)
        self.assertLess(ewma_point.bounded_multiplier, rolling_point.bounded_multiplier)

    def test_zero_volatility_does_not_create_unbounded_size(self):
        sizer = VolatilitySizer(self._config())
        point = sizer.build_schedule([0.0] * 25)[20]
        self.assertFalse(point.ready)
        self.assertEqual(point.reason, "REALIZED_VOLATILITY_ZERO_OR_INVALID")

    def test_base_risk_above_layer6_cap_is_rejected(self):
        sizer = VolatilitySizer(self._config())
        with self.assertRaisesRegex(ValueError, "BASE_RISK_PCT_OUTSIDE_LAYER6_CAP"):
            sizer.build_schedule([0.01, -0.01] * 20, base_risk_pct=0.025)

    def test_audit_record_is_non_authoritative(self):
        sizer = VolatilitySizer(self._config())
        point = sizer.build_schedule([0.01, -0.01] * 12)[20]
        record = point.audit_record(
            trade_id="research-trade-1",
            asset_class="financial",
            timestamp_utc="2026-11-09T12:00:00Z",
        )
        self.assertFalse(record["capital_authority_granted"])
        self.assertFalse(record["order_submission_permitted"])
        self.assertTrue(record["research_only"])


class EntryControlTests(unittest.TestCase):
    def _ready_point(self):
        returns = [0.01 if i % 2 == 0 else -0.01 for i in range(25)]
        return VolatilitySizer(VolatilitySizingConfig(
            periods_per_year=1, target_vol_annual=0.01, window=20
        )).build_schedule(returns)[20]

    def test_financial_entry_requires_requested_session(self):
        point = self._ready_point()
        decision = evaluate_research_entry_controls(
            signal_timestamp="2026-01-15T13:30:00Z",
            asset_class="financial",
            volatility_point=point,
            required_session="LONDON",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "OUTSIDE_REQUIRED_FINANCIAL_SESSION")

    def test_synthetic_entry_bypasses_session_but_keeps_volatility_gate(self):
        point = self._ready_point()
        decision = evaluate_research_entry_controls(
            signal_timestamp="2026-01-15T07:30:00Z",
            asset_class="synthetic",
            volatility_point=point,
            required_session="LONDON",
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.session_label, "SYNTHETIC_BYPASS")
        self.assertFalse(decision.capital_authority)
        self.assertFalse(decision.order_submission_permitted)

    def test_unready_volatility_estimate_blocks_both_asset_classes(self):
        sizer = VolatilitySizer(VolatilitySizingConfig(periods_per_year=1))
        point = sizer.build_schedule([0.01, -0.01])[1]
        decision = evaluate_research_entry_controls(
            signal_timestamp="2026-01-15T13:30:00Z",
            asset_class="synthetic",
            volatility_point=point,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "VOLATILITY_SIZER_NOT_READY")


class ResearchCandidateIntegrationTests(unittest.TestCase):
    class Candidate:
        research_only = True
        capital_authority = False
        order_submission_permitted = False
        signal_timestamp_utc = "2026-01-15T07:30:00Z"

    def _schedule(self):
        returns = [0.01 if i % 2 == 0 else -0.01 for i in range(25)]
        sizer = VolatilitySizer(VolatilitySizingConfig(
            periods_per_year=1, target_vol_annual=0.01, window=20
        ))
        return sizer.build_schedule(returns)

    def test_candidate_adapter_applies_financial_session_and_lagged_size(self):
        result = prepare_candidate_for_research_simulation(
            self.Candidate(),
            signal_timestamp="2026-01-15T07:30:00Z",
            asset_class="financial",
            volatility_schedule=self._schedule(),
            entry_bar_index=20,
            required_session="LONDON",
        )
        self.assertTrue(result.decision.allowed)
        self.assertEqual(result.decision.session_label, "LONDON")
        self.assertIsNotNone(result.effective_risk_pct)
        self.assertFalse(result.audit_record(candidate_id="candidate-1")["order_submission_permitted"])

    def test_canonical_strategy_candidate_payload_is_accepted_as_research_only(self):
        candidate = StrategyCandidate(
            strategy_id="MSNR_LIQUIDITY_SWEEP",
            version="1.0.0",
            direction="LONG",
            signal_timestamp_utc="2026-01-15T07:30:00Z",
            entry_timing="NEXT_BAR_OPEN_AFTER_SIGNAL",
            stop_reference_price=99.0,
            target_reference_price=102.0,
            target_mode="FIXED",
            regime="TRENDING_LOW_VOL",
            evidence_codes=("CLOSED_BAR_SIGNAL",),
        )
        result = prepare_candidate_for_research_simulation(
            candidate,
            signal_timestamp="2026-01-15T07:30:00Z",
            asset_class="financial",
            volatility_schedule=self._schedule(),
            entry_bar_index=20,
            required_session="LONDON",
        )
        self.assertTrue(result.decision.allowed)
        self.assertIs(result.candidate, candidate)

    def test_candidate_adapter_bypasses_financial_session_for_synthetics(self):
        result = prepare_candidate_for_research_simulation(
            self.Candidate(),
            signal_timestamp="2026-01-15T07:30:00Z",
            asset_class="synthetic",
            volatility_schedule=self._schedule(),
            entry_bar_index=20,
            required_session="LONDON",
        )
        self.assertTrue(result.decision.allowed)
        self.assertEqual(result.decision.session_label, "SYNTHETIC_BYPASS")

    def test_financial_session_label_is_a_categorical_column_when_pandas_is_available(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas is not installed")
        frame = pd.DataFrame(
            {"timestamp_utc": ["2026-01-15T07:30:00Z", "2026-01-15T10:30:00Z"]}
        )
        result = apply_session_filter(
            frame, "financial", timestamp_column="timestamp_utc"
        )
        self.assertTrue(isinstance(result["session_label"].dtype, pd.CategoricalDtype))
        self.assertEqual(result["session_label"].tolist(), ["LONDON", "DEAD"])

    def test_candidate_adapter_rejects_timestamp_not_bound_to_candidate(self):
        candidate = self.Candidate()
        result = prepare_candidate_for_research_simulation
        with self.assertRaisesRegex(ValueError, "CANDIDATE_SIGNAL_TIMESTAMP_MISMATCH"):
            result(
                candidate,
                signal_timestamp="2026-01-15T07:31:00Z",
                asset_class="financial",
                volatility_schedule=self._schedule(),
                entry_bar_index=20,
                required_session="LONDON",
            )

    def test_candidate_adapter_rejects_non_research_or_authoritative_candidate(self):
        class UnsafeCandidate:
            research_only = True
            capital_authority = True
            order_submission_permitted = False
            signal_timestamp_utc = "2026-01-15T07:30:00Z"

        with self.assertRaisesRegex(ValueError, "CAPITAL_AUTHORITY_FORBIDDEN"):
            prepare_candidate_for_research_simulation(
                UnsafeCandidate(),
                signal_timestamp="2026-01-15T07:30:00Z",
                asset_class="financial",
                volatility_schedule=self._schedule(),
                entry_bar_index=20,
            )


class FalsificationTestTests(unittest.TestCase):
    def _daily(self, value):
        return {f"2026-01-{day:02d}": [value] * 5 for day in range(1, 31)}

    def test_c_is_skipped_for_synthetics(self):
        result = test_c_session_edge(
            asset_class="synthetic", day_ids=[], daily_trade_r={}
        )
        self.assertEqual(result["verdict"], "SKIPPED")

    def test_c_passes_only_when_london_ci_is_above_baseline_and_asian(self):
        daily = {
            "LONDON": self._daily(0.50),
            "NY_AM": self._daily(0.10),
            "ASIAN": self._daily(-0.30),
            "BASELINE": self._daily(0.0),
        }
        result = test_c_session_edge(
            asset_class="financial",
            day_ids=sorted(self._daily(0.0)),
            daily_trade_r=daily,
            replications=500,
            minimum_trades=100,
            minimum_days=30,
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertGreater(
            result["sessions"]["LONDON"]["expectancy_ci95_lower"],
            result["sessions"]["BASELINE"]["expectancy_ci95_upper"],
        )

    def test_c_fails_when_london_does_not_outperform_baseline(self):
        daily = {
            "LONDON": self._daily(0.10),
            "NY_AM": self._daily(0.05),
            "ASIAN": self._daily(-0.10),
            "BASELINE": self._daily(0.20),
        }
        result = test_c_session_edge(
            asset_class="financial",
            day_ids=sorted(self._daily(0.0)),
            daily_trade_r=daily,
            replications=500,
        )
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["reason"], "LONDON_EDGE_NOT_ESTABLISHED")

    def test_c_fails_closed_for_insufficient_trade_count(self):
        daily = {
            "LONDON": self._daily(0.50),
            "NY_AM": self._daily(0.10),
            "ASIAN": self._daily(-0.30),
            "BASELINE": self._daily(0.0),
        }
        daily["LONDON"] = {day: [] for day in daily["LONDON"]}
        result = test_c_session_edge(
            asset_class="financial",
            day_ids=sorted(self._daily(0.0)),
            daily_trade_r=daily,
            replications=500,
        )
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("TRADE_COUNT_INSUFFICIENT", result["reason"])

    def test_estimator_selection_requires_real_dsr_values_and_both_trials(self):
        missing = select_volatility_estimator_from_dsr(
            rolling_dsr=None, ewma_dsr=None,
            rolling_trade_count=200, ewma_trade_count=200,
            configurations_tested=2,
        )
        self.assertEqual(missing["status"], "NOT_RUN")
        selected = select_volatility_estimator_from_dsr(
            rolling_dsr=0.90, ewma_dsr=0.95,
            rolling_trade_count=200, ewma_trade_count=200,
            configurations_tested=2,
        )
        self.assertEqual(selected["selected_estimator"], "ewma")
        tied = select_volatility_estimator_from_dsr(
            rolling_dsr=0.90, ewma_dsr=0.91,
            rolling_trade_count=200, ewma_trade_count=200,
            configurations_tested=2,
        )
        self.assertEqual(tied["selected_estimator"], "rolling")


if __name__ == "__main__":
    unittest.main()
