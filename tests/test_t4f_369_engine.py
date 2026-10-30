"""Unit tests for deterministic T4F x 369 primitives."""
import unittest
from decimal import Decimal

from research.labs.t4f_369_engine import (
    OHLC,
    calculate_369_step,
    classify_m15_level_interaction,
    detect_confirmed_pivot_candidates,
    digital_root_for_reference,
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

    def test_lower_wick_rejection(self):
        bar = OHLC.from_values("16", "17", "14", "15.5")
        self.assertEqual(classify_m15_level_interaction(bar, "15"), "LOWER_WICK_REJECTION")

    def test_pivot_candidate_is_available_only_after_right_window(self):
        highs = [1, 2, 3, 8, 4, 3, 2]
        lows =  [0, 1, 2,  3, 2, 1, 1]
        candidates = detect_confirmed_pivot_candidates(
            highs, lows, left_bars=2, right_bars=2
        )
        high_candidate = next(item for item in candidates if item.pivot_type == "HIGH")
        self.assertEqual(high_candidate.pivot_index, 3)
        self.assertEqual(high_candidate.confirmation_index, 5)
        self.assertEqual(high_candidate.status, "CANDIDATE_NOT_PROTECTED")


if __name__ == "__main__":
    unittest.main()
