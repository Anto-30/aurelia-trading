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

    @patch("tools.external_repo_sync.urllib.request.urlopen")
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

    @patch("tools.external_repo_sync.urllib.request.urlopen")
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

    @patch("tools.external_repo_sync.urllib.request.urlopen")
    @patch("tools.external_repo_sync.subprocess.run")
    def test_rest_404_remains_a_blocking_failure(self, run_git, urlopen):
        run_git.return_value = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout="", stderr="remote: Repository not found."
        )
        urlopen.side_effect = HTTPError("https://api.github.com", 404, "not found", {}, None)
        result = check_repository(RECORD)
        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "REST_API_HTTP_404")


if __name__ == "__main__":
    unittest.main()
