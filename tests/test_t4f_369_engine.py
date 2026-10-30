"""Unit tests for deterministic T4F x 369 primitives."""
import unittest
from decimal import Decimal

from research.labs.t4f_369_engine import (
    OHLC,
    calculate_369_step,
    classify_m15_level_interaction,
    detect_confirmed_pivot_candidates,
    digital_root_for_reference,
    classify_opening_reference_bias,
    new_york_369_session_markers,
    classify_nq_es_smt,
    first_aligned_fvg_candidate,
)


class T4F369EngineTests(unittest.TestCase):
    def test_digital_root_uses_integer_part_only(self):
        self.assertEqual(digital_root_for_reference("4217.395"), (4217, 14, 5))

    def test_xau_bearish_projection_uses_full_reference_price(self):
        projection = calculate_369_step("4217.395", "XAUUSD", "bearish")
        self.assertEqual(projection.base_step, Decimal("15"))
        self.assertEqual(projection.levels, tuple(
            Decimal(v) for v in ("4202.395", "4187.395", "4172.395", "4157.395")
        ))

    def test_bullish_xau_projection(self):
        projection = calculate_369_step("4066.535", "XAUUSD", "bullish")
        self.assertEqual(projection.digital_root, 7)
        self.assertEqual(projection.base_step, Decimal("12"))
        self.assertEqual(projection.levels[0], Decimal("4078.535"))

    def test_nq_scaling_is_ten_times(self):
        projection = calculate_369_step("25417.25", "NQ", "bearish")
        self.assertEqual(projection.digital_root, 1)
        self.assertEqual(projection.scaled_step, Decimal("120"))

    def test_es_scaling_flag_is_explicitly_unverified(self):
        projection = calculate_369_step("5217.50", "ES", "bullish")
        self.assertEqual(projection.instrument_multiplier, Decimal("1"))
        self.assertEqual(projection.calibration_status, "UNVERIFIED_PER_USER_SPEC")

    def test_unknown_instrument_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "INSTRUMENT_MAPPING_UNDEFINED"):
            calculate_369_step("100", "CL", "bullish")

    def test_non_positive_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "REFERENCE_PRICE_MUST_BE_POSITIVE"):
            digital_root_for_reference("0")

    def test_fractional_price_below_one_has_no_positive_integer_part(self):
        with self.assertRaisesRegex(ValueError, "DIGITAL_ROOT_UNDEFINED_FOR_ZERO_REFERENCE"):
            digital_root_for_reference("0.5")

    def test_at_least_four_levels_required(self):
        with self.assertRaisesRegex(ValueError, "AT_LEAST_FOUR_LEVELS_REQUIRED"):
            calculate_369_step("4217.395", "XAUUSD", "bearish", 3)

    def test_body_cross_above_not_promoted_to_decisive(self):
        bar = OHLC.from_values("14", "17", "13", "16")
        self.assertEqual(
            classify_m15_level_interaction(bar, "15"),
            "BODY_CROSS_ABOVE_DECISIVENESS_UNDEFINED",
        )

    def test_upper_wick_rejection_is_not_entry_signal(self):
        bar = OHLC.from_values("14", "16", "13", "14.5")
        self.assertEqual(classify_m15_level_interaction(bar, "15"), "UPPER_WICK_REJECTION")

    def test_opening_references_both_above_means_look_for_sell(self):
        result = classify_opening_reference_bias("105", "100", "102")
        self.assertEqual(result.day_open_action, "LOOK_FOR_SELL")
        self.assertEqual(result.london_open_action, "LOOK_FOR_SELL")
        self.assertEqual(result.combined_bias, "BEARISH")

    def test_conflicting_opening_references_are_neutral(self):
        result = classify_opening_reference_bias("101", "100", "102")
        self.assertEqual(result.combined_bias, "NEUTRAL")

    def test_exact_new_york_369_time_markers(self):
        from datetime import date
        markers = dict(new_york_369_session_markers(date(2026, 10, 30)))
        self.assertEqual(markers["0.000"], "2026-10-30T07:20:00-04:00")
        self.assertEqual(markers["0.315"], "2026-10-30T08:24:34.500000-04:00")
        self.assertEqual(markers["0.630"], "2026-10-30T09:29:09-04:00")
        self.assertEqual(markers["0.810"], "2026-10-30T10:06:03-04:00")
        self.assertEqual(markers["1.000"], "2026-10-30T10:45:00-04:00")

    def test_nq_lower_low_without_es_lower_low_is_bullish_smt(self):
        result = classify_nq_es_smt(
            nq_prior_high="100", nq_prior_low="90",
            nq_current_high="99", nq_current_low="89",
            es_prior_high="500", es_prior_low="490",
            es_current_high="499", es_current_low="491",
        )
        self.assertEqual(result.classification, "BULLISH_SMT")

    def test_nq_higher_high_without_es_higher_high_is_bearish_smt(self):
        result = classify_nq_es_smt(
            nq_prior_high="100", nq_prior_low="90",
            nq_current_high="101", nq_current_low="91",
            es_prior_high="500", es_prior_low="490",
            es_current_high="499", es_current_low="491",
        )
        self.assertEqual(result.classification, "BEARISH_SMT")

    def test_first_fvg_is_after_confirmation_and_midpoint_is_exact(self):
        bars = [
            OHLC.from_values("10", "11", "9", "10"),
            OHLC.from_values("10", "11", "9", "10"),
            OHLC.from_values("9.5", "10", "9", "9.8"),
            OHLC.from_values("10", "11.5", "9.8", "11.2"),
            OHLC.from_values("12.5", "13", "12", "12.8"),
        ]
        fvg = first_aligned_fvg_candidate(bars, direction="bullish", confirmation_bar_index=1)
        self.assertIsNotNone(fvg)
        self.assertEqual((fvg.first_bar_index, fvg.third_bar_index), (2, 4))
        self.assertEqual(fvg.gap_low, Decimal("10"))
        self.assertEqual(fvg.gap_high, Decimal("12"))
        self.assertEqual(fvg.midpoint, Decimal("11"))
        self.assertEqual(fvg.status, "FVG_CANDIDATE_RULE_REQUIRES_OWNER_FREEZE")

    def test_no_fvg_before_confirmation_is_promoted(self):
        bars = [
            OHLC.from_values("9", "10", "8", "9"),
            OHLC.from_values("11", "12", "11", "12"),
            OHLC.from_values("13", "14", "13", "14"),
        ]
        self.assertIsNone(
            first_aligned_fvg_candidate(bars, direction="bullish", confirmation_bar_index=1)
        )

    def test_lower_wick_rejection(self):
        bar = OHLC.from_values("16", "17", "14", "15.5")
        self.assertEqual(classify_m15_level_interaction(bar, "15"), "LOWER_WICK_REJECTION")

    def test_pivot_candidate_is_available_only_after_right_window(self):
        highs = [10, 11, 12, 18, 14, 13, 12]
        lows =  [8, 7, 6, 4, 7, 8, 9]
        candidates = detect_confirmed_pivot_candidates(
            highs, lows, left_bars=2, right_bars=2
        )
        high_candidate = next(item for item in candidates if item.pivot_type == "HIGH")
        self.assertEqual(high_candidate.pivot_index, 3)
        self.assertEqual(high_candidate.confirmation_index, 5)
        self.assertEqual(high_candidate.status, "CANDIDATE_NOT_PROTECTED")


if __name__ == "__main__":
    unittest.main()
