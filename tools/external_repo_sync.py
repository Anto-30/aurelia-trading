from __future__ import annotations

"""Fail-closed external repository reachability probe with a public REST fallback.

This module only reads repository metadata. It never checks out, installs, or
executes external repository code.
"""

import json
import re
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _validate_source(record: dict[str, Any]) -> tuple[str, str] | None:
    repo = record.get("repo")
    source_url = record.get("source_url")
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
        return None
    if not isinstance(source_url, str):
        return None
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if path != repo or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return None
    return repo, source_url


def _classify_git_failure(stderr: str) -> str:
    text = (stderr or "").lower()
    if "repository not found" in text or "not found" in text:
        return "REMOTE_REPOSITORY_NOT_FOUND"
    if "could not resolve host" in text or "temporary failure in name resolution" in text:
        return "GIT_DNS_FAILURE"
    if "timed out" in text or "timeout" in text:
        return "GIT_PROBE_TIMEOUT"
    if "connection reset" in text or "connection refused" in text or "remote end hung up" in text:
        return "GIT_TRANSPORT_FAILURE"
    if "rate limit" in text or "429" in text:
        return "GIT_RATE_LIMITED"
    return "GIT_PROBE_NONZERO"


def _rest_default_branch_tip(repo: str, timeout: int = 15) -> str:
    # This is deliberately an anonymous, public metadata read; no credentials or
    # repository code are involved. It is invoked only when git ls-remote fails.
    query = urlencode({"per_page": "1"})
    url = f"https://api.github.com/repos/{repo}/commits?{query}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AURELIA-External-Repository-Sync",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("REST_COMMIT_LIST_EMPTY")
    sha = payload[0].get("sha") if isinstance(payload[0], dict) else None
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise ValueError("REST_COMMIT_SHA_INVALID")
    return sha


def check_repository(record: dict[str, Any], *, git_timeout: int = 20) -> dict[str, Any]:
    validated = _validate_source(record)
    repo = str(record.get("repo", ""))[:160]
    if validated is None:
        return {
            "repo": repo,
            "reachable": False,
            "error": "INVALID_REPOSITORY_SOURCE",
        }
    repo, source_url = validated
    git_error = "GIT_PROBE_NONZERO"

    # A hard repository-not-found response is not retried through Git; it falls
    # back to GitHub's public REST metadata endpoint before being marked failed.
    for attempt in range(2):
        try:
            result = subprocess.run(
                ["git", "ls-remote", source_url, "HEAD"],
                text=True,
                capture_output=True,
                timeout=git_timeout,
                check=False,
            )
            if result.returncode == 0:
                first_line = next((line for line in result.stdout.splitlines() if line.strip()), "")
                fields = first_line.split()
                sha = fields[0] if fields else ""
                if len(fields) >= 2 and SHA_RE.fullmatch(sha):
                    return {
                        "repo": repo,
                        "reachable": True,
                        "head_commit": sha,
                        "reachability_method": "git_ls_remote",
                        "git_probe_error": None,
                    }
                git_error = "GIT_RESPONSE_INVALID"
            else:
                git_error = _classify_git_failure(result.stderr)
        except subprocess.TimeoutExpired:
            git_error = "GIT_PROBE_TIMEOUT"
        except OSError:
            git_error = "GIT_EXECUTION_ERROR"

        if git_error == "REMOTE_REPOSITORY_NOT_FOUND":
            break
        if attempt == 0:
            time.sleep(1)

    try:
        sha = _rest_default_branch_tip(repo)
        return {
            "repo": repo,
            "reachable": True,
            "head_commit": sha,
            "reachability_method": "github_public_rest_fallback",
            "git_probe_error": git_error,
        }
    except HTTPError as exc:
        rest_error = f"REST_API_HTTP_{int(exc.code)}"
    except (URLError, TimeoutError):
        rest_error = "REST_API_NETWORK_ERROR"
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        rest_error = "REST_API_RESPONSE_INVALID"
    except Exception:
        rest_error = "REST_API_PROBE_ERROR"

    return {
        "repo": repo,
        "reachable": False,
        "error": rest_error,
        "git_probe_error": git_error,
    }


def main() -> int:
    from pathlib import Path

    policy = json.loads(Path("config/external_repo_federation.json").read_text(encoding="utf-8"))
    repositories = policy.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        print("EXTERNAL_REPO_SYNC=BLOCKED")
        print("EXTERNAL_REPO_SYNC_REASON=MANIFEST_EMPTY_OR_INVALID")
        return 2

    # Keep probe concurrency below the previous 16-worker burst to reduce
    # transient remote failures and anonymous REST fallback rate pressure.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check_repository, repositories))

    output = {
        "schema": "aurelia.external_repo_sync.v1",
        "repositories": results,
    }
    Path("/tmp/external-repo-sync.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failed = [row for row in results if not row.get("reachable")]
    unresolved = [
        row for row in repositories
        if row.get("head_commit") == "SYNC_REQUIRED"
    ]
    print(f"EXTERNAL_REPO_REACHABLE={len(results) - len(failed)}/{len(results)}")
    print(f"EXTERNAL_REPO_PINNED={len(repositories) - len(unresolved)}/{len(repositories)}")
    print(f"EXTERNAL_REPO_UNRESOLVED_PIN_COUNT={len(unresolved)}")
    fallback_count = sum(row.get("reachability_method") == "github_public_rest_fallback" for row in results)
    print(f"EXTERNAL_REPO_REST_FALLBACKS={fallback_count}")
    if failed:
        # Print names and classified error codes only; never echo raw upstream responses.
        print("UNREACHABLE_REPOSITORIES=" + json.dumps([
            {"repo": row["repo"], "error": row.get("error"), "git_probe_error": row.get("git_probe_error")}
            for row in failed
        ], sort_keys=True))
        print("EXTERNAL_REPO_SYNC=BLOCKED")
        return 1
    print("EXTERNAL_REPO_SYNC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
