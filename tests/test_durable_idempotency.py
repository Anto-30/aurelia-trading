import tempfile
import unittest
from pathlib import Path

from runtime.core.idempotency import IdempotencyStore


class DurableIdempotencyTests(unittest.TestCase):
    def test_accepted_intent_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            first = IdempotencyStore(path)
            first.register_intent("intent-1")
            first.attach_broker_transaction("intent-1", "tx-1")
            first.record_economic_effect("intent-1")

            second = IdempotencyStore(path)
            record = second.get("intent-1")
            self.assertIsNotNone(record)
            self.assertEqual(record.broker_transaction_id, "tx-1")
            self.assertEqual(record.economic_effect_count, 1)

    def test_unknown_outcome_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            first = IdempotencyStore(path)
            first.register_intent("intent-unknown")
            first.record_unknown_outcome("intent-unknown")

            second = IdempotencyStore(path)
            record = second.get("intent-unknown")
            self.assertTrue(record.broker_outcome_unknown)
            self.assertEqual(record.economic_effect_count, 0)


if __name__ == "__main__":
    unittest.main()
