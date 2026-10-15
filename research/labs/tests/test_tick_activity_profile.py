import unittest

from tick_activity_profile import (
    PriceObservation,
    calculate_tick_activity_profile,
)


class TickActivityProfileTests(unittest.TestCase):
    def calc(self, rows, **kwargs):
        defaults = dict(
            symbol="TEST",
            tick_size="0.1",
            bin_width_ticks=1,
            anchor_start_time=0,
            as_of_time=100,
            value_area_fraction="0.70",
        )
        defaults.update(kwargs)
        return calculate_tick_activity_profile(rows, **defaults)

    def test_labels_proxy_and_never_live_eligible(self):
        p = self.calc([PriceObservation(1, "1.0")])
        self.assertEqual(p.semantics_label, "PRICE_VISIT_ACTIVITY_PROXY")
        self.assertEqual(p.data_source_kind, "TICK_PRICE_OBSERVATIONS")
        self.assertFalse(p.live_eligible)

    def test_as_of_cutoff_excludes_future_observations(self):
        rows = [PriceObservation(1, "1.0"), PriceObservation(2, "1.1"),
                PriceObservation(101, "9.9")]
        p = self.calc(rows, as_of_time=2)
        self.assertEqual(p.observation_count, 2)
        self.assertNotIn((99, 1), p.bins)

    def test_anchor_cutoff_excludes_earlier_observations(self):
        rows = [PriceObservation(1, "9.0"), PriceObservation(2, "1.0")]
        p = self.calc(rows, anchor_start_time=2)
        self.assertEqual(p.observation_count, 1)
        self.assertEqual(p.activity_poc, "1")

    def test_non_monotonic_timestamps_rejected(self):
        rows = [PriceObservation(2, "1.0"), PriceObservation(1, "1.1")]
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            self.calc(rows)

    def test_empty_window_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_OBSERVATIONS"):
            self.calc([PriceObservation(101, "1.0")])

    def test_invalid_tick_size_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TICK_SIZE"):
            self.calc([PriceObservation(1, "1.0")], tick_size="0")

    def test_price_not_aligned_to_tick_rejected(self):
        with self.assertRaisesRegex(ValueError, "PRICE_NOT_ALIGNED"):
            self.calc([PriceObservation(1, "1.05")], tick_size="0.1")

    def test_poc_and_value_area_ordering(self):
        rows = ([PriceObservation(i, "1.0") for i in range(1, 8)] +
                [PriceObservation(8, "0.9"), PriceObservation(9, "1.1")])
        p = self.calc(rows)
        self.assertLessEqual(float(p.activity_val), float(p.activity_poc))
        self.assertLessEqual(float(p.activity_poc), float(p.activity_vah))

    def test_deterministic_hash_and_levels(self):
        rows = [PriceObservation(1, "1.0"), PriceObservation(2, "1.1"),
                PriceObservation(3, "1.0")]
        p1, p2 = self.calc(rows), self.calc(rows)
        self.assertEqual(p1.raw_observation_sha256, p2.raw_observation_sha256)
        self.assertEqual(p1.to_dict(), p2.to_dict())

    def test_duplicate_timestamps_are_preserved(self):
        rows = [PriceObservation(1, "1.0"), PriceObservation(1, "1.0")]
        p = self.calc(rows)
        self.assertEqual(p.observation_count, 2)
        self.assertEqual(p.bins, ((10, 2),))


if __name__ == "__main__":
    unittest.main()
