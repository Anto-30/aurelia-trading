from __future__ import annotations

import math
import unittest
from datetime import datetime, timezone

from research.r100_prospective_oos_collector import (
    initial_state,
    observe_tick,
)


class NullHunter:
    def observe(self, **kwargs):
        return None


class ResearchRegressionTests(unittest.TestCase):
    def test_collector_rejects_nonfinite_and_nonpositive_market_quotes(self):
        invalid_quotes = (math.nan, math.inf, -math.inf, 0.0, -1.0)
        for quote in invalid_quotes:
            with self.subTest(quote=quote):
                with self.assertRaisesRegex(
                    ValueError,
                    "R100_TICK_QUOTE_INVALID",
                ):
                    observe_tick(
                        hunter=NullHunter(),
                        state=initial_state(),
                        quote=quote,
                        received_at=datetime.now(timezone.utc),
                    )

    def test_collector_rejects_timezone_naive_tick_timestamps(self):
        with self.assertRaisesRegex(
            ValueError,
            "R100_TICK_TIMESTAMP_TIMEZONE_REQUIRED",
        ):
            observe_tick(
                hunter=NullHunter(),
                state=initial_state(),
                quote=100.0,
                received_at=datetime(2026, 11, 5, 12, 0, 0),
            )


if __name__ == "__main__":
    unittest.main()
