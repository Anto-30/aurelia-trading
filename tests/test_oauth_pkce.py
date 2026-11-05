from __future__ import annotations

import base64
import hashlib
import re
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from runtime.oauth.pkce import PKCEChallenge, PKCEMethod
from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.client import _RejectOAuthRedirectHandler


def write_allowlist(path: Path, *, redirect_uris=None, permitted=None, authorize=None):
    redirects = redirect_uris if redirect_uris is not None else [
        "https://aurelia.example.com/oauth/callback"
    ]
    scopes = permitted if permitted is not None else ["trade"]
    lines = [
        "oauth_application:",
        "  name: aurelia-trading-runtime",
        "  provider: deriv",
        "  app_id_env_var: DERIV_OAUTH_APP_ID",
        "  redirect_uris: []" if not redirects else "  redirect_uris:",
        *[f'    - "{uri}"' for uri in redirects],
        "token_scope:",
        "  permitted:",
        *[f'    - "{scope}"' for scope in scopes],
        "endpoints:",
        f'  authorize: "{authorize or "https://auth.deriv.com/oauth2/auth"}"',
        '  token: "https://auth.deriv.com/oauth2/token"',
        "token_policy:",
        "  pending_authorization_ttl_seconds: 600",
        "  max_access_token_ttl_seconds: 7776000",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class OAuthPKCETests(unittest.TestCase):
    def test_pkce_generation_uses_s256_and_rfc7636_verifier_shape(self):
        challenge = PKCEChallenge.generate()
        self.assertTrue(challenge.validate())
        self.assertGreaterEqual(len(challenge.code_verifier), 43)
        self.assertLessEqual(len(challenge.code_verifier), 128)
        self.assertRegex(challenge.code_verifier, re.compile(r"^[A-Za-z0-9._~-]+$"))
        self.assertEqual(len(challenge.code_challenge), 43)
        self.assertEqual(challenge.code_challenge_method, PKCEMethod.S256)
        digest = hashlib.sha256(challenge.code_verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        self.assertEqual(challenge.code_challenge, expected)
        self.assertTrue(challenge.verify_challenge())
        self.assertGreaterEqual(len(challenge.state), 32)

    def test_pkce_rejects_plain_and_malformed_values(self):
        challenge = PKCEChallenge(
            code_verifier="A" * 43,
            code_challenge="B" * 43,
            code_challenge_method="plain",
            state="S" * 43,
        )
        with self.assertRaisesRegex(ValueError, "S256"):
            challenge.validate_method()
        malformed = PKCEChallenge(
            code_verifier="short",
            code_challenge="not-a-challenge",
            code_challenge_method="S256",
            state="short",
        )
        with self.assertRaises(ValueError):
            malformed.validate()

    def test_pkce_challenge_comparison_is_false_after_verifier_tampering(self):
        challenge = PKCEChallenge.generate()
        tampered = PKCEChallenge(
            code_verifier="Z" * len(challenge.code_verifier),
            code_challenge=challenge.code_challenge,
            code_challenge_method="S256",
            state=challenge.state,
        )
        self.assertFalse(tampered.verify_challenge())

    def test_allowlist_requires_exact_https_redirect_and_trade_scope(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "oauth_allowlist.yaml"
            write_allowlist(config)
            allowlist = OAuthAllowlist.load(
                str(config), environ={"DERIV_OAUTH_APP_ID": "test-app-123"}
            )
            self.assertEqual(allowlist.app_id, "test-app-123")
            self.assertTrue(allowlist.validate_redirect_uri(
                "https://aurelia.example.com/oauth/callback"
            ))
            self.assertFalse(allowlist.validate_redirect_uri(
                "https://aurelia.example.com/oauth/callback/extra"
            ))
            self.assertFalse(allowlist.validate_redirect_uri(
                "https://evil.example.com/oauth/callback"
            ))
            self.assertTrue(allowlist.validate_scopes(["trade"]))
            self.assertFalse(allowlist.validate_scopes(["trade", "read"]))
            self.assertFalse(allowlist.validate_scopes(["account_manage"]))
            self.assertFalse(allowlist.validate_scopes(["application_read"]))
            self.assertFalse(allowlist.validate_scopes(["payment"]))

    def test_allowlist_fails_closed_when_no_redirect_is_registered(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "oauth_allowlist.yaml"
            write_allowlist(config, redirect_uris=[])
            with self.assertRaisesRegex(ValueError, "REDIRECT_URI_ALLOWLIST_EMPTY"):
                OAuthAllowlist.load(
                    str(config), environ={"DERIV_OAUTH_APP_ID": "test-app-123"}
                )

    def test_allowlist_rejects_untrusted_authorization_endpoint(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "oauth_allowlist.yaml"
            write_allowlist(
                config, authorize="https://oauth.deriv.com/oauth2/authorize"
            )
            with self.assertRaisesRegex(ValueError, "OAUTH_ENDPOINT_NOT_TRUSTED"):
                OAuthAllowlist.load(
                    str(config), environ={"DERIV_OAUTH_APP_ID": "test-app-123"}
                )

    def test_token_endpoint_redirect_handler_never_follows_redirects(self):
        handler = _RejectOAuthRedirectHandler()
        request = Request("https://auth.deriv.com/oauth2/token")
        redirected = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://attacker.example/collect",
        )
        self.assertIsNone(redirected)


if __name__ == "__main__":
    unittest.main()
