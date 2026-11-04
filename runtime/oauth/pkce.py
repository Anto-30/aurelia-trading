from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Final, Literal


class PKCEMethod:
    """Supported PKCE method constants. S256 is the only permitted method."""

    S256: Final[Literal["S256"]] = "S256"


_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_CHALLENGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


@dataclass(frozen=True)
class PKCEChallenge:
    """A PKCE S256 challenge with an independent CSRF state value."""

    code_verifier: str
    code_challenge: str
    code_challenge_method: Literal["S256"]
    state: str

    @classmethod
    def generate(cls) -> "PKCEChallenge":
        # 32 bytes encode to 43 unpadded base64url characters.
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(32)
        result = cls(
            code_verifier=verifier,
            code_challenge=challenge,
            code_challenge_method=PKCEMethod.S256,
            state=state,
        )
        result.validate()
        return result

    def validate_method(self) -> bool:
        if self.code_challenge_method != PKCEMethod.S256:
            raise ValueError("PKCE_METHOD_FORBIDDEN_ONLY_S256_SUPPORTED")
        return True

    def validate(self) -> bool:
        self.validate_method()
        if not isinstance(self.code_verifier, str) or not _VERIFIER_PATTERN.fullmatch(self.code_verifier):
            raise ValueError("PKCE_CODE_VERIFIER_INVALID")
        if not isinstance(self.code_challenge, str) or not _CHALLENGE_PATTERN.fullmatch(self.code_challenge):
            raise ValueError("PKCE_CODE_CHALLENGE_INVALID")
        if not isinstance(self.state, str) or not _STATE_PATTERN.fullmatch(self.state):
            raise ValueError("PKCE_STATE_INVALID")
        return True

    def verify_challenge(self) -> bool:
        try:
            self.validate()
            digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
            expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        except (UnicodeEncodeError, TypeError, ValueError):
            return False
        return hmac.compare_digest(expected, self.code_challenge)
