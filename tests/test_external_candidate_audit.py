"""Regression tests for isolated external-candidate scanner configuration."""

import os
import unittest
from pathlib import Path

from tools.audit_external_candidates import docker_common_args, safe_tool_failure_class


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


if __name__ == "__main__":
    unittest.main()
