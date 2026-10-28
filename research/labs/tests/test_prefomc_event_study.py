import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from research.labs.prefomc_event_study import run_study, summarize

NY = ZoneInfo("America/New_York")


def ts(day, hour=14, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY)


class PreFOMCEventStudyTests(unittest.TestCase):
    def test_uses_previous_available_trading_session_and_1400_exit(self):
        prior = date(2026, 10, 27)
        meeting = date(2026, 10, 28)
        bars = {ts(prior): 100.0, ts(meeting): 101.0}
        rows = run_study(bars, [{"meeting_date": meeting, "announcement_at": "2026-10-28T14:15:00-04:00"}], 0.0)
        self.assertEqual(rows[0]["status"], "OK")
        self.assertEqual(rows[0]["entry_timestamp"], ts(prior).isoformat())
        self.assertEqual(rows[0]["exit_timestamp"], ts(meeting).isoformat())
        self.assertAlmostEqual(float(rows[0]["gross_return"]), 0.01)

    def test_cost_haircut_reduces_return(self):
        d1, d2 = date(2026, 10, 27), date(2026, 10, 28)
        bars = {ts(d1, 13, 45): 100.0, ts(d2, 13, 45): 101.0}
        event = [{"meeting_date": d2, "announcement_at": "2026-10-28T14:00:00-04:00"}]
        gross = float(run_study(bars, event, 0.0)[0]["net_return"])
        net = float(run_study(bars, event, 5.0)[0]["net_return"])
        self.assertLess(net, gross)

    def test_partial_intermediate_date_is_not_treated_as_previous_session(self):
        prior = date(2026, 10, 26)
        partial = date(2026, 10, 27)
        meeting = date(2026, 10, 28)
        bars = {
            ts(prior): 100.0,
            ts(partial, 13, 59): 999.0,  # partial session with no 14:00 reference bar
            ts(meeting): 101.0,
        }
        rows = run_study(bars, [{"meeting_date": meeting, "announcement_at": "2026-10-28T14:15:00-04:00"}], 0.0)
        self.assertEqual(rows[0]["status"], "OK")
        self.assertEqual(rows[0]["entry_timestamp"], ts(prior).isoformat())
        self.assertAlmostEqual(float(rows[0]["gross_return"]), 0.01)

    def test_missing_exact_bar_is_excluded_not_interpolated(self):
        d1, d2 = date(2026, 10, 27), date(2026, 10, 28)
        bars = {ts(d1, 13, 45): 100.0, ts(d2, 14, 1): 101.0}
        rows = run_study(bars, [{"meeting_date": d2, "announcement_at": "2026-10-28T14:00:00-04:00"}], 0.0)
        self.assertEqual(rows[0]["status"], "MISSING_EXACT_REFERENCE_BAR")
        self.assertEqual(rows[0]["net_return"], "")

    def test_1400_release_uses_1345_reference_window(self):
        prior, meeting = date(2026, 10, 27), date(2026, 10, 28)
        bars = {ts(prior, 13, 45): 100.0, ts(meeting, 13, 45): 101.0}
        rows = run_study(bars, [{"meeting_date": meeting, "announcement_at": "2026-10-28T14:00:00-04:00"}], 0.0)
        self.assertEqual(rows[0]["status"], "OK")
        self.assertEqual(rows[0]["entry_timestamp"], ts(prior, 13, 45).isoformat())
        self.assertEqual(rows[0]["exit_timestamp"], ts(meeting, 13, 45).isoformat())
        self.assertAlmostEqual(float(rows[0]["gross_return"]), 0.01)

    def test_missing_announcement_timestamp_is_excluded(self):
        prior, meeting = date(2026, 10, 27), date(2026, 10, 28)
        bars = {ts(prior): 100.0, ts(meeting): 101.0}
        rows = run_study(bars, [{"meeting_date": meeting, "announcement_at": ""}], 0.0)
        self.assertEqual(rows[0]["status"], "MISSING_ANNOUNCEMENT_TIMESTAMP")
        self.assertEqual(rows[0]["net_return"], "")

    def test_summary_is_research_only_and_does_not_claim_p_value(self):
        rows = [{"status": "OK", "net_return": "0.01"}]
        summary = summarize(rows)
        self.assertTrue(summary["research_only"])
        self.assertFalse(summary["capital_authority"])
        self.assertFalse(summary["live_execution"])
        self.assertIsNone(summary["p_value"])

    def test_cost_must_be_nonnegative(self):
        with self.assertRaises(ValueError):
            run_study({}, [], -1.0)


if __name__ == "__main__":
    unittest.main()
