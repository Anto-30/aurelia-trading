from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from assurance.github_review_verifier import verify_independent_security_review


SOURCE_SHA = "a" * 40


def record() -> dict:
    return {
        "independent_review_reference": (
            "https://github.com/Anto-30/aurelia-trading/pull/292"
            "#pullrequestreview-77"
        ),
        "reviewed_commit": SOURCE_SHA,
        "independent_reviewer": "security-reviewer",
        "auditor": "Anto-30",
    }


def api_response(payload: dict) -> io.BytesIO:
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def pull_payload(head_sha: str = SOURCE_SHA) -> dict:
    return {
        "number": 292,
        "state": "open",
        "user": {"login": "Anto-30"},
        "head": {"sha": head_sha},
    }


def review_payload(
    *,
    state: str = "APPROVED",
    reviewer: str = "security-reviewer",
    commit_sha: str = SOURCE_SHA,
) -> dict:
    return {
        "id": 77,
        "state": state,
        "user": {"login": reviewer},
        "commit_id": commit_sha,
        "submitted_at": "2026-11-14T16:00:00Z",
    }


class GitHubReviewVerifierTests(unittest.TestCase):
    def _verify(self, record_value: dict, pull: dict, review: dict):
        with patch.dict(
            "os.environ",
            {
                "GITHUB_REPOSITORY": "Anto-30/aurelia-trading",
                "GITHUB_TOKEN": "synthetic-read-only-token",
            },
            clear=True,
        ), patch(
            "assurance.github_review_verifier.urlopen",
            side_effect=[api_response(pull), api_response(review)],
        ):
            return verify_independent_security_review(
                record_value,
                expected_source_sha=SOURCE_SHA,
            )

    def test_exact_head_approved_by_distinct_human_is_verified(self):
        ok, detail = self._verify(record(), pull_payload(), review_payload())
        self.assertTrue(ok)
        self.assertEqual(detail, "GITHUB_INDEPENDENT_REVIEW_VERIFIED")

    def test_comment_or_changes_requested_review_is_not_approval(self):
        ok, detail = self._verify(
            record(),
            pull_payload(),
            review_payload(state="COMMENTED"),
        )
        self.assertFalse(ok)
        self.assertEqual(detail, "GITHUB_REVIEW_NOT_APPROVED")

    def test_pr_author_cannot_supply_independent_approval(self):
        ok, detail = self._verify(
            record(),
            pull_payload(),
            review_payload(reviewer="Anto-30"),
        )
        self.assertFalse(ok)
        self.assertEqual(detail, "GITHUB_REVIEWER_IDENTITY_MISMATCH")

    def test_approval_on_stale_commit_is_rejected(self):
        ok, detail = self._verify(
            record(),
            pull_payload(head_sha="b" * 40),
            review_payload(),
        )
        self.assertFalse(ok)
        self.assertEqual(detail, "PULL_REQUEST_HEAD_DOES_NOT_MATCH_CANDIDATE")

    def test_review_on_another_commit_is_rejected(self):
        ok, detail = self._verify(
            record(),
            pull_payload(),
            review_payload(commit_sha="b" * 40),
        )
        self.assertFalse(ok)
        self.assertEqual(detail, "GITHUB_REVIEW_COMMIT_DOES_NOT_MATCH_CANDIDATE")

    def test_missing_api_token_fails_closed_without_network_call(self):
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "Anto-30/aurelia-trading"}, clear=True), patch(
            "assurance.github_review_verifier.urlopen"
        ) as opener:
            ok, detail = verify_independent_security_review(
                record(),
                expected_source_sha=SOURCE_SHA,
            )
        self.assertFalse(ok)
        self.assertEqual(detail, "GITHUB_REVIEW_VERIFICATION_TOKEN_UNAVAILABLE")
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
