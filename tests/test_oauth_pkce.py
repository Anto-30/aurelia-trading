from __future__ import annotations

import base64
import hashlib
import re

import pytest

from runtime.oauth.pkce import PKCEChallenge, PKCEMethod
from runtime.oauth.allowlist import OAuthAllowlist


def _write_allowlist(path, *, redirect_uris=None, permitted=None, authorize=None):
    redirects = redirect_uris if redirect_uris is not None else ["https://aurelia.example.com/oauth/callback"]
    scopes = permitted if permitted is not None else ["trade"]
    path.write_text(
        """oauth_application:
  name: aurelia-trading-runtime
  provider: deriv
  app_id_env_var: DERIV_OAUTH_APP_ID
  redirect_uris:
"""
        + "".join(f"    - \"{uri}\"\n" for uri in redirects)
        + """token_scope:
  permitted:
"""
        + "".join(f"    - \"{scope}\"\n" for scope in scopes)
        + """endpoints:
  authorize: \""""
        + (authorize or "https://auth.deriv.com/oauth2/auth")
        + """\"
  token: \"https://auth.deriv.com/oauth2/token\"
token_policy:
  pending_authorization_ttl_seconds: 600
  max_access_token_ttl_seconds: 7776000
""",
        encoding="utf-8",
    )


def test_pkce_generation_uses_s256_and_rfc7636_verifier_shape():
    challenge = PKCEChallenge.generate()

    assert challenge.validate_method() is True
    assert 43 <= len(challenge.code_verifier) <= 128
    assert re.fullmatch(r"[A-Za-z0-9._~-]+", challenge.code_verifier)
    assert len(challenge.code_challenge) == 43
    assert challenge.code_challenge_method == PKCEMethod.S256
    digest = hashlib.sha256(challenge.code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert challenge.code_challenge == expected
    assert challenge.verify_challenge() is True
    assert len(challenge.state) >= 32


def test_pkce_rejects_plain_and_malformed_values():
    challenge = PKCEChallenge(
        code_verifier="A" * 43,
        code_challenge="B" * 43,
        code_challenge_method="plain",
        state="S" * 32,
    )
    with pytest.raises(ValueError, match="S256"):
        challenge.validate_method()

    malformed = PKCEChallenge(
        code_verifier="short",
        code_challenge="not-a-challenge",
        code_challenge_method="S256",
        state="short",
    )
    with pytest.raises(ValueError):
        malformed.validate()


def test_pkce_challenge_comparison_is_false_after_verifier_tampering():
    challenge = PKCEChallenge.generate()
    tampered = PKCEChallenge(
        code_verifier="Z" * len(challenge.code_verifier),
        code_challenge=challenge.code_challenge,
        code_challenge_method="S256",
        state=challenge.state,
    )
    assert tampered.verify_challenge() is False


def test_allowlist_requires_exact_https_redirect_and_trade_scope(tmp_path):
    config = tmp_path / "oauth_allowlist.yaml"
    _write_allowlist(config)
    allowlist = OAuthAllowlist.load(
        str(config),
        environ={"DERIV_OAUTH_APP_ID": "test-app-123"},
    )

    assert allowlist.app_id == "test-app-123"
    assert allowlist.validate_redirect_uri(
        "https://aurelia.example.com/oauth/callback"
    ) is True
    assert allowlist.validate_redirect_uri(
        "https://aurelia.example.com/oauth/callback/extra"
    ) is False
    assert allowlist.validate_redirect_uri(
        "https://evil.example.com/oauth/callback"
    ) is False
    assert allowlist.validate_scopes(["trade"]) is True
    assert allowlist.validate_scopes(["trade", "read"]) is False
    assert allowlist.validate_scopes(["account_manage"]) is False
    assert allowlist.validate_scopes(["application_read"]) is False
    assert allowlist.validate_scopes(["payment"]) is False


def test_allowlist_fails_closed_when_no_real_redirect_is_registered(tmp_path):
    config = tmp_path / "oauth_allowlist.yaml"
    _write_allowlist(config, redirect_uris=[])
    with pytest.raises(ValueError, match="REDIRECT_URI_ALLOWLIST_EMPTY"):
        OAuthAllowlist.load(
            str(config),
            environ={"DERIV_OAUTH_APP_ID": "test-app-123"},
        )


def test_allowlist_rejects_untrusted_authorization_endpoint(tmp_path):
    config = tmp_path / "oauth_allowlist.yaml"
    _write_allowlist(config, authorize="https://oauth.deriv.com/oauth2/authorize")
    with pytest.raises(ValueError, match="OAUTH_ENDPOINT_NOT_TRUSTED"):
        OAuthAllowlist.load(
            str(config),
            environ={"DERIV_OAUTH_APP_ID": "test-app-123"},
        )
