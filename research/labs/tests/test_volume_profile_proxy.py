import unittest

from research.labs.volume_profile_proxy import (
    CAPITAL_AUTHORITY,
    LIVE_EXECUTION,
    RESEARCH_ONLY,
    VolumeProfileInputError,
    calculate_tick_activity_profile,
    classify_price_context,
    detect_node_candidates,
    profile_to_dict,
)


def ticks(prices, start=1_800_000_000):
    return [{"price": p, "epoch": start + i} for i, p in enumerate(prices)]


class TickActivityProfileTests(unittest.TestCase):
    def test_profile_labels_proxy_and_never_authorizes_execution(self):
        profile = calculate_tick_activity_profile(
            ticks([100, 100, 100, 101, 102, 101]),
            instrument="TEST",
            data_source="fixture",
            num_bins=4,
        )
        self.assertEqual(profile.profile_kind, "TICK_ACTIVITY_PROXY")
        self.assertEqual(profile.total_ticks, 6)
        self.assertTrue(profile.research_only)
        self.assertTrue(RESEARCH_ONLY)
        self.assertFalse(CAPITAL_AUTHORITY)
        self.assertFalse(LIVE_EXECUTION)

    def test_total_ticks_reconcile_and_bins_are_monotonic(self):
        profile = calculate_tick_activity_profile(ticks([1, 1, 2, 2, 3]), num_bins=5)
        self.assertEqual(sum(row.tick_count for row in profile.bins), profile.total_ticks)
        self.assertEqual(profile.total_ticks, 5)
        for left, right in zip(profile.bins, profile.bins[1:]):
            self.assertLess(left.lower_edge, left.upper_edge)
            self.assertEqual(left.upper_edge, right.lower_edge)

    def test_fixed_price_width_is_repeatable(self):
        rows = ticks([100.01, 100.02, 100.03, 100.02])
        first = calculate_tick_activity_profile(rows, bin_width=0.01)
        second = calculate_tick_activity_profile(rows, bin_width=0.01)
        self.assertEqual(first.bins, second.bins)
        self.assertEqual(first.binning_method, "FIXED_PRICE_WIDTH")
        self.assertAlmostEqual(first.bin_width, 0.01)

    def test_flat_prices_do_not_create_zero_width_bins(self):
        profile = calculate_tick_activity_profile(ticks([50, 50, 50]), num_bins=10)
        self.assertEqual(profile.total_ticks, 3)
        self.assertTrue(all(row.upper_edge > row.lower_edge for row in profile.bins))
        self.assertIn("DEGENERATE", profile.binning_method)

    def test_value_area_expands_at_first_bin_and_through_empty_bins(self):
        # Regression: the supplied loop can fail to advance when POC is at a boundary.
        profile = calculate_tick_activity_profile(
            ticks([1, 1, 1, 1, 10, 10, 10, 10]), num_bins=10
        )
        self.assertGreaterEqual(profile.value_area_fraction_actual, 0.70)
        self.assertLessEqual(profile.val, profile.poc)
        self.assertLessEqual(profile.poc, profile.vah)
        self.assertEqual(
            profile.value_area_tick_count,
            sum(row.tick_count for row in profile.bins
                if profile.val_bin_index <= row.index <= profile.vah_bin_index),
        )

    def test_value_area_fraction_one_includes_entire_profile(self):
        profile = calculate_tick_activity_profile(ticks([10, 11, 15, 20]), value_area_fraction=1)
        self.assertEqual(profile.value_area_tick_count, profile.total_ticks)
        self.assertEqual(profile.val_bin_index, 0)
        self.assertEqual(profile.vah_bin_index, len(profile.bins) - 1)

    def test_node_detection_returns_candidates_not_signals(self):
        prices = [0.5] + [1.5] * 4 + [2.5] + [4.5] + [5.5] * 5
        profile = calculate_tick_activity_profile(ticks(prices), num_bins=6)
        nodes = detect_node_candidates(profile)
        self.assertTrue(any(n.kind == "HVN_CANDIDATE" and n.bin_index == 1 for n in nodes))
        self.assertTrue(any(n.kind == "LVN_CANDIDATE" and n.bin_index == 3 for n in nodes))
        self.assertTrue(all("CANDIDATE" in n.kind for n in nodes))

    def test_price_context_is_not_a_trade_signal(self):
        profile = calculate_tick_activity_profile(ticks([1, 1, 2, 2, 3, 3]), num_bins=3)
        self.assertIn(classify_price_context(profile.poc, profile), {
            "INSIDE_VALUE_AREA", "ABOVE_VAH", "BELOW_VAL"
        })
        self.assertNotIn("trade_signal", profile_to_dict(profile))

    def test_empty_or_malformed_input_fails_closed(self):
        with self.assertRaisesRegex(VolumeProfileInputError, "NO_TICK_DATA"):
            calculate_tick_activity_profile([])
        with self.assertRaisesRegex(VolumeProfileInputError, "TICK_PRICE_AND_EPOCH_REQUIRED"):
            calculate_tick_activity_profile([{"price": 1}])
        with self.assertRaisesRegex(VolumeProfileInputError, "PRICE_NONFINITE"):
            calculate_tick_activity_profile([{"price": float("nan"), "epoch": 1}])

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaisesRegex(VolumeProfileInputError, "VALUE_AREA_FRACTION_OUT_OF_RANGE"):
            calculate_tick_activity_profile(ticks([1, 2]), value_area_fraction=0)
        with self.assertRaisesRegex(VolumeProfileInputError, "BIN_WIDTH_MUST_BE_POSITIVE"):
            calculate_tick_activity_profile(ticks([1, 2]), bin_width=0)
        with self.assertRaisesRegex(VolumeProfileInputError, "NUM_BINS_MUST_BE_POSITIVE_INTEGER"):
            calculate_tick_activity_profile(ticks([1, 2]), num_bins=0)

    def test_epoch_order_is_normalized(self):
        data = [{"price": 101, "epoch": 5}, {"price": 100, "epoch": 3}]
        profile = calculate_tick_activity_profile(data)
        self.assertEqual(profile.profile_start_epoch, 3)
        self.assertEqual(profile.profile_end_epoch, 5)


if __name__ == "__main__":
    unittest.main()
