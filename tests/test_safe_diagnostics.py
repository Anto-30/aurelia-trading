import unittest
from pathlib import Path

from runtime.core.safe_diagnostics import safe_exception_frames


class SafeExceptionFrameTests(unittest.TestCase):
    def test_reports_file_line_and_function_without_exception_message(self):
        secret_sentinel = "DO_NOT_LOG_SECRET_SENTINEL"

        def failing_operation():
            raise ValueError(secret_sentinel)

        try:
            failing_operation()
        except ValueError as exc:
            frames = safe_exception_frames(exc, root=Path.cwd())

        rendered = "\n".join(frames)
        self.assertIn("test_reports_file_line_and_function_without_exception_message", rendered)
        self.assertIn(":", rendered)
        self.assertNotIn(secret_sentinel, rendered)
        self.assertNotIn("ValueError", rendered)

    def test_empty_traceback_produces_no_frames(self):
        exc = ValueError("DO_NOT_LOG_SECRET_SENTINEL")
        self.assertEqual(safe_exception_frames(exc, root=Path.cwd()), ())

    def test_frame_limit_is_enforced(self):
        def outer():
            def inner():
                raise ValueError("safe test")

            inner()

        try:
            outer()
        except ValueError as exc:
            frames = safe_exception_frames(exc, root=Path.cwd(), limit=1)
        self.assertEqual(len(frames), 1)


if __name__ == "__main__":
    unittest.main()
