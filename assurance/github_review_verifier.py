from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class GitHubReviewVerificationError(ValueError):
    pass


def _api_json(url: str, token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AURELIA-certification-review-verifier",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=8) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubReviewVerificationError(
            f"GITHUB_REVIEW_API_UNAVAILABLE:{type(exc).__name__}"
        ) from exc
    if not isinstance(value, dict):
        raise GitHubReviewVerificationError("GITHUB_REVIEW_API_INVALID_RESPONSE")
    return value


def verify_independent_security_review(
    record: dict[str, Any],
    *,
    expected_source_sha: str,
    repository: str | None = None,
    token: str | None = None,
) -> tuple[bool, str]:
    """Verify an approval from GitHub itself; never trust JSON approval fields alone."""
    repository = (repository if repository is not None else os.getenv("GITHUB_REPOSITORY", "")).strip()
    token = (token if token is not None else os.getenv("GITHUB_TOKEN", "")).strip()
    if not token:
        return False, "GITHUB_REVIEW_VERIFICATION_TOKEN_UNAVAILABLE"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return False, "GITHUB_REPOSITORY_UNAVAILABLE_OR_INVALID"
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
        return False, "CANDIDATE_SOURCE_SHA_INVALID"

    reference = record.get("independent_review_reference")
    if not isinstance(reference, str):
        return False, "INDEPENDENT_REVIEW_REFERENCE_MISSING"
    parts = urlsplit(reference)
    path = parts.path.strip("/").split("/")
    if (
        parts.scheme != "https"
        or parts.netloc.lower() != "github.com"
        or len(path) != 4
        or path[2] != "pull"
        or not path[3].isdigit()
        or int(path[3]) < 1
        or not parts.fragment.startswith("pullrequestreview-")
        or not parts.fragment.removeprefix("pullrequestreview-").isdigit()
        or int(parts.fragment.removeprefix("pullrequestreview-")) < 1
    ):
        return False, "INDEPENDENT_REVIEW_REFERENCE_INVALID"

    referenced_repository = f"{path[0]}/{path[1]}"
    if referenced_repository.casefold() != repository.casefold():
        return False, "INDEPENDENT_REVIEW_REPOSITORY_MISMATCH"
    pull_number = int(path[3])
    review_id = int(parts.fragment.removeprefix("pullrequestreview-"))

    if record.get("reviewed_commit") != expected_source_sha:
        return False, "REVIEWED_COMMIT_DOES_NOT_MATCH_CANDIDATE"
    reviewer = record.get("independent_reviewer")
    auditor = record.get("auditor")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or reviewer.strip().lower().endswith("[bot]")
        or not isinstance(auditor, str)
        or not auditor.strip()
        or reviewer.strip().casefold() == auditor.strip().casefold()
    ):
        return False, "INDEPENDENT_REVIEWER_IDENTITY_INVALID"

    api_root = f"https://api.github.com/repos/{repository}/pulls/{pull_number}"
    try:
        pull = _api_json(api_root, token)
        review = _api_json(f"{api_root}/reviews/{review_id}", token)
    except GitHubReviewVerificationError as exc:
        return False, str(exc)

    author = pull.get("user", {}).get("login") if isinstance(pull.get("user"), dict) else None
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    review_user = review.get("user") if isinstance(review.get("user"), dict) else {}
    review_login = review_user.get("login")
    if author is None or not isinstance(author, str) or not author.strip():
        return False, "PULL_REQUEST_AUTHOR_UNAVAILABLE"
    if head.get("sha") != expected_source_sha:
        return False, "PULL_REQUEST_HEAD_DOES_NOT_MATCH_CANDIDATE"
    if review.get("id") != review_id:
        return False, "GITHUB_REVIEW_ID_MISMATCH"
    if str(review.get("state", "")).upper() != "APPROVED":
        return False, "GITHUB_REVIEW_NOT_APPROVED"
    if not isinstance(review_login, str) or review_login.casefold() != reviewer.strip().casefold():
        return False, "GITHUB_REVIEWER_IDENTITY_MISMATCH"
    if review_login.casefold() == author.casefold():
        return False, "PULL_REQUEST_AUTHOR_CANNOT_SELF_APPROVE"
    if review_login.lower().endswith("[bot]"):
        return False, "GITHUB_BOT_REVIEW_NOT_INDEPENDENT"
    if review.get("commit_id") != expected_source_sha:
        return False, "GITHUB_REVIEW_COMMIT_DOES_NOT_MATCH_CANDIDATE"
    submitted_at = review.get("submitted_at")
    if not isinstance(submitted_at, str) or not submitted_at.strip():
        return False, "GITHUB_REVIEW_SUBMISSION_TIME_MISSING"

    return True, "GITHUB_INDEPENDENT_REVIEW_VERIFIED"
