"""Regression tests for isolated external-candidate scanner configuration."""

import os
import unittest
from pathlib import Path

from tools.audit_external_candidates import (
    docker_common_args,
    safe_tool_failure_class,
    semgrep_coverage_status,
    sanitize_semgrep,
    trivy_database_args,
)


class SemgrepCoverageTests(unittest.TestCase):
    def test_no_scanner_errors_is_complete(self):
        self.assertEqual(semgrep_coverage_status([]), "COMPLETED")

    def test_partial_parsing_warning_is_not_reported_complete(self):
        self.assertEqual(
            semgrep_coverage_status([{"level": "warn", "type": "PartialParsing", "code": 3}]),
            "PARTIAL_BLOCKED",
        )

    def test_scanner_timeout_is_not_reported_complete(self):
        self.assertEqual(
            semgrep_coverage_status([{"level": "warn", "type": "Timeout", "code": 2}]),
            "PARTIAL_BLOCKED",
        )

    def test_semgrep_report_surfaces_coverage_limitation_without_raw_error_text(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [],
            "errors": [{
                "level": "warn",
                "code": 2,
                "type": "Timeout",
                "message": "sensitive raw diagnostic",
            }],
        })
        self.assertEqual(report["status"], "PARTIAL_BLOCKED")
        self.assertEqual(report["scanner_error_count"], 1)
        self.assertNotIn("sensitive raw diagnostic", str(report))


class AuditDockerEnvironmentTests(unittest.TestCase):
    def test_git_global_config_uses_writable_container_tmpfs(self):
        args = docker_common_args(
            "semgrep/semgrep:1.182.0",
            "semgrep",
            Path("/tmp/aurelia-source"),
            Path("/tmp/aurelia-scan"),
            Path("/tmp/aurelia-cache"),
        )
        env_values = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "-e"]
        tmpfs_values = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "--tmpfs"]

        user_index = args.index("--user")
        self.assertRegex(args[user_index + 1], r"^\d+:\d+$")
        self.assertIn("HOME=/tmp", env_values)
        self.assertIn("GIT_CONFIG_GLOBAL=/tmp/.gitconfig", env_values)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", env_values)
        self.assertIn("GIT_TERMINAL_PROMPT=0", env_values)
        self.assertIn("XDG_CONFIG_HOME=/tmp/.config", env_values)
        self.assertIn("XDG_CACHE_HOME=/tmp/.cache", env_values)
        self.assertIn("/tmp:rw,nosuid,nodev,size=512m", tmpfs_values)
        # A writable temporary home is needed by Semgrep builds that use /root directly.
        self.assertIn(
            f"/root:rw,nosuid,nodev,size=128m,uid={os.getuid()},gid={os.getgid()},mode=700",
            tmpfs_values,
        )
        self.assertNotIn("/root/.semgrep:rw,nosuid,nodev,size=16m", tmpfs_values)

    def test_trivy_database_fetch_failures_have_a_specific_safe_code(self):
        # The scanner must identify the failing security-database layer without exposing raw diagnostics.
        self.assertEqual(
            safe_tool_failure_class("failed to download vulnerability db: context deadline exceeded", ""),
            "TRIVY_VULNERABILITY_DB_FETCH_FAILED",
        )

    def test_trivy_checks_bundle_fetch_failures_have_a_specific_safe_code(self):
        self.assertEqual(
            safe_tool_failure_class("failed to download checks bundle: registry request failed", ""),
            "TRIVY_CHECKS_BUNDLE_FETCH_FAILED",
        )

    def test_trivy_uses_official_vulnerability_database_fallbacks(self):
        args = trivy_database_args()
        repositories = [args[i + 1] for i, item in enumerate(args[:-1]) if item == "--db-repository"]
        self.assertEqual(
            repositories,
            [
                "public.ecr.aws/aquasecurity/trivy-db",
                "mirror.gcr.io/aquasec/trivy-db",
                "ghcr.io/aquasecurity/trivy-db",
                "aquasec/trivy-db",
            ],
        )

    def test_trivy_uses_official_java_database_fallbacks_and_checks_bundle(self):
        args = trivy_database_args()
        java_repositories = [
            args[i + 1] for i, item in enumerate(args[:-1]) if item == "--java-db-repository"
        ]
        self.assertEqual(len(java_repositories), 4)
        self.assertEqual(
            java_repositories[0], "public.ecr.aws/aquasecurity/trivy-java-db"
        )
        checks_index = args.index("--checks-bundle-repository")
        self.assertEqual(args[checks_index + 1], "public.ecr.aws/aquasecurity/trivy-checks")


if __name__ == "__main__":
    unittest.main()
