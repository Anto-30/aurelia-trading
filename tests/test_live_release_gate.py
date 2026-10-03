import unittest

import scripts.live_release_gate as gate


class LiveReleaseGateTests(unittest.TestCase):
    def test_current_repository_is_fail_closed(self):
        with self.assertRaises(RuntimeError) as ctx:
            gate.check_certification_evidence()
        self.assertIn("strict certification evidence block", str(ctx.exception))

    def test_release_gate_cannot_use_missing_session_evidence(self):
        original = gate.SESSION_EVIDENCE_PATH
        try:
            gate.SESSION_EVIDENCE_PATH = gate.ROOT / "artifacts" / "definitely-missing-session.json"
            with self.assertRaises(RuntimeError):
                gate.check_session_evidence()
        finally:
            gate.SESSION_EVIDENCE_PATH = original


if __name__ == "__main__":
    unittest.main()
