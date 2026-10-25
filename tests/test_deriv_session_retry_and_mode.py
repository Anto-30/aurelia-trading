import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import call, patch

from runtime.adapters import deriv_session


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._payload


def git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return hashlib.sha1(header + raw).hexdigest()


def write_lock(path: Path, *, mode="VERIFY_ONLY", live="BLOCKED", authorized="false", enabled="false"):
    path.write_text(
        "\n".join(
            (
                "schema: aurelia.live_lock.v1",
                f"live_trading_enabled: {enabled}",
                f"FINAL_EXECUTION_AUTHORIZATION: {authorized}",
                f"LIVE_EXECUTION: {live}",
                f"capital_plane_mode: {mode}",
            )
        )
        + "\n",
        encoding="utf-8",
    )


class DerivOtpRetryAndModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lock_path = Path(self.temp.name) / "LIVE_LOCK.yaml"
        write_lock(self.lock_path)
        self.lock_patch = patch.object(deriv_session, "LIVE_LOCK_PATH", self.lock_path)
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.hash_patch = patch.object(
            deriv_session, "EXPECTED_LIVE_LOCK_BLOB_SHA", git_blob_sha(self.lock_path)
        )
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def write_test_lock(self, **kwargs) -> None:
        write_lock(self.lock_path, **kwargs)
        # Semantic mutation tests explicitly attest to their fixture hash.
        deriv_session.EXPECTED_LIVE_LOCK_BLOB_SHA = git_blob_sha(self.lock_path)

    def test_transient_network_drops_retry_with_bounded_exponential_backoff(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            if len(calls) == 1:
                raise URLError("simulated socket drop")
            if len(calls) == 2:
                raise TimeoutError("simulated response timeout")
            return FakeResponse(
                {"data": {"url": "wss://api.derivws.com/trading/v1/options/ws/demo?otp=FIXTURE_ONLY"}}
            )

        with patch.dict("os.environ", {"DERIV_AUTH_MODE": "pat"}), patch.object(
            deriv_session, "urlopen", side_effect=fake_urlopen
        ) as mocked_urlopen, patch.object(deriv_session.time, "sleep") as sleep:
            session = deriv_session.get_authenticated_ws_url(
                "VRTC12345",
                bearer_token="fixture-token-never-real",
                app_id="fixture-app-id",
            )

        self.assertEqual(session.account_id, "VRTC12345")
        self.assertEqual(len(calls), 3)
        self.assertEqual(mocked_urlopen.call_count, 3)
        sleep.assert_has_calls([call(0.25), call(0.5)])
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(session.safe_url(), "wss://api.derivws.com/trading/v1/options/ws/demo")
        self.assertNotIn("FIXTURE_ONLY", session.safe_url())

    def test_http_400_is_not_retried_and_error_is_sanitized(self):
        bad_request = HTTPError(
            "https://api.derivws.com/trading/v1/options/accounts/VRTC12345/otp",
            400,
            "Bad Request",
            hdrs=None,
            fp=None,
        )
        with patch.dict("os.environ", {"DERIV_AUTH_MODE": "pat"}), patch.object(
            deriv_session, "urlopen", side_effect=bad_request
        ) as mocked_urlopen, patch.object(deriv_session.time, "sleep") as sleep:
            with self.assertRaisesRegex(deriv_session.DerivSessionError, "OTP_REQUEST_REJECTED_HTTP_400") as caught:
                deriv_session.get_authenticated_ws_url(
                    "VRTC12345",
                    bearer_token="fixture-token-never-real",
                    app_id="fixture-app-id",
                )

        self.assertEqual(mocked_urlopen.call_count, 1)
        sleep.assert_not_called()
        self.assertNotIn("fixture-token-never-real", str(caught.exception))
        self.assertNotIn("api.derivws.com", str(caught.exception))

    def test_non_verify_only_mode_makes_no_authenticated_rest_call(self):
        self.write_test_lock(mode="BLOCKED")
        with patch.dict("os.environ", {"DERIV_AUTH_MODE": "pat"}), patch.object(
            deriv_session, "urlopen"
        ) as mocked_urlopen:
            with self.assertRaisesRegex(
                deriv_session.DerivSessionError,
                "CAPITAL_PLANE_MODE_NOT_VERIFY_ONLY",
            ):
                deriv_session.get_authenticated_ws_url(
                    "VRTC12345",
                    bearer_token="fixture-token-never-real",
                    app_id="fixture-app-id",
                )
        mocked_urlopen.assert_not_called()

    def test_unreadable_or_incomplete_lock_makes_no_authenticated_rest_call(self):
        self.lock_path.write_text("schema: aurelia.live_lock.v1\n", encoding="utf-8")
        deriv_session.EXPECTED_LIVE_LOCK_BLOB_SHA = git_blob_sha(self.lock_path)
        with patch.object(deriv_session, "urlopen") as mocked_urlopen:
            with self.assertRaisesRegex(deriv_session.DerivSessionError, "LIVE_LOCK_STATE_UNKNOWN"):
                deriv_session.get_authenticated_ws_url(
                    "VRTC12345",
                    bearer_token="fixture-token-never-real",
                    app_id="fixture-app-id",
                )
        mocked_urlopen.assert_not_called()

    def test_modified_lock_blob_is_rejected_even_if_required_flags_look_safe(self):
        # A comment-only change preserves visible flags but invalidates the exact canonical Git blob identity.
        self.lock_path.write_text(
            self.lock_path.read_text(encoding="utf-8") + "# unapproved modification\n",
            encoding="utf-8",
        )
        with patch.object(deriv_session, "urlopen") as mocked_urlopen:
            with self.assertRaisesRegex(
                deriv_session.DerivSessionError, "LIVE_LOCK_BLOB_SHA_MISMATCH"
            ):
                deriv_session.get_authenticated_ws_url(
                    "VRTC12345",
                    bearer_token="fixture-token-never-real",
                    app_id="fixture-app-id",
                )
        mocked_urlopen.assert_not_called()

    def test_final_authorization_must_remain_false(self):
        self.write_test_lock(authorized="true")
        with patch.object(deriv_session, "urlopen") as mocked_urlopen:
            with self.assertRaisesRegex(deriv_session.DerivSessionError, "LIVE_LOCK_NOT_FAIL_CLOSED"):
                deriv_session.get_authenticated_ws_url(
                    "VRTC12345",
                    bearer_token="fixture-token-never-real",
                    app_id="fixture-app-id",
                )
        mocked_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
