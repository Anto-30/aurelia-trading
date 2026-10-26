from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from tools.external_repo_sync import check_repository


VALID_SHA = "a" * 40
RECORD = {
    "repo": "owner/project",
    "source_url": "https://github.com/owner/project",
}


class ExternalRepositorySyncTests(unittest.TestCase):
    @patch("tools.external_repo_sync.time.sleep")
    @patch("tools.external_repo_sync.subprocess.run")
    def test_git_ls_remote_success_is_used_without_rest_fallback(self, run_git, sleep):
        run_git.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout=f"{VALID_SHA}\tHEAD\n", stderr=""
        )
        result = check_repository(RECORD)
        self.assertTrue(result["reachable"])
        self.assertEqual(result["head_commit"], VALID_SHA)
        self.assertEqual(result["reachability_method"], "git_ls_remote")
        self.assertIsNone(result["git_probe_error"])
        sleep.assert_not_called()

    @patch("tools.external_repo_sync.urlopen")
    @patch("tools.external_repo_sync.time.sleep")
    @patch("tools.external_repo_sync.subprocess.run")
    def test_public_rest_fallback_recovers_git_repository_not_found(self, run_git, sleep, urlopen):
        run_git.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="",
            stderr="remote: Repository not found.\nfatal: repository unavailable"
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps([{"sha": VALID_SHA}]).encode()
        urlopen.return_value = response
        result = check_repository(RECORD)
        self.assertTrue(result["reachable"])
        self.assertEqual(result["head_commit"], VALID_SHA)
        self.assertEqual(result["reachability_method"], "github_public_rest_fallback")
        self.assertEqual(result["git_probe_error"], "REMOTE_REPOSITORY_NOT_FOUND")
        sleep.assert_not_called()
        self.assertEqual(urlopen.call_count, 1)

    @patch("tools.external_repo_sync.urlopen")
    @patch("tools.external_repo_sync.time.sleep")
    @patch("tools.external_repo_sync.subprocess.run")
    def test_transient_git_failure_is_retried_before_rest_fallback(self, run_git, sleep, urlopen):
        run_git.side_effect = [
            subprocess.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="Connection timed out"),
            subprocess.CompletedProcess(args=["git"], returncode=0, stdout=f"{VALID_SHA}\tHEAD\n", stderr=""),
        ]
        result = check_repository(RECORD)
        self.assertTrue(result["reachable"])
        self.assertEqual(result["reachability_method"], "git_ls_remote")
        self.assertEqual(run_git.call_count, 2)
        sleep.assert_called_once_with(1)
        urlopen.assert_not_called()

    @patch("tools.external_repo_sync.subprocess.run")
    def test_invalid_source_url_is_rejected_before_network_access(self, run_git):
        record = {**RECORD, "source_url": "https://example.invalid/owner/project"}
        result = check_repository(record)
        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "INVALID_REPOSITORY_SOURCE")
        run_git.assert_not_called()

    @patch("tools.external_repo_sync.urlopen")
    @patch("tools.external_repo_sync.subprocess.run")
    def test_rest_404_remains_a_blocking_failure(self, run_git, urlopen):
        run_git.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="", stderr="remote: Repository not found."
        )
        urlopen.side_effect = HTTPError("https://api.github.com", 404, "not found", {}, None)
        result = check_repository(RECORD)
        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "REST_API_HTTP_404")



    @patch("tools.external_repo_sync.subprocess.run")
    def test_unavailable_reference_only_source_is_exempted_but_not_counted_reachable(self, run_git):
        record = {
            "repo": "NetroIndonesia/freebuff2api",
            "source_url": "https://github.com/NetroIndonesia/freebuff2api",
            "mode": "REFERENCE_ONLY",
            "sync_enabled": False,
            "sync_exemption_reason": (
                "The public GitHub REST repository endpoint returned HTTP 404 on 2026-10-26. "
                "Retain the last known pin for provenance only; do not install or execute. "
                "Re-enable sync only after independent URL and commit verification."
            ),
            "sync_exemption_observed_at_utc": "2026-10-26T09:40:04Z",
        }
        result = check_repository(record)
        self.assertFalse(result["reachable"])
        self.assertTrue(result["exempted"])
        self.assertEqual(result["status"], "REFERENCE_ONLY_UNAVAILABLE")
        run_git.assert_not_called()

    @patch("tools.external_repo_sync.subprocess.run")
    def test_unknown_or_unapproved_exemption_remains_blocked(self, run_git):
        record = {
            "repo": "owner/project",
            "source_url": "https://github.com/owner/project",
            "mode": "REFERENCE_ONLY",
            "sync_enabled": False,
            "sync_exemption_reason": "please skip",
            "sync_exemption_observed_at_utc": "2026-10-26T00:00:00Z",
        }
        result = check_repository(record)
        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "INVALID_REFERENCE_ONLY_EXEMPTION")
        run_git.assert_not_called()

if __name__ == "__main__":
    unittest.main()
