"""Regression tests for isolated external-candidate scanner configuration."""

import unittest
from pathlib import Path

from tools.audit_external_candidates import docker_common_args


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

        self.assertIn("HOME=/tmp", env_values)
        self.assertIn("GIT_CONFIG_GLOBAL=/tmp/.gitconfig", env_values)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", env_values)
        self.assertIn("GIT_TERMINAL_PROMPT=0", env_values)
        self.assertIn("XDG_CONFIG_HOME=/tmp/.config", env_values)
        self.assertIn("XDG_CACHE_HOME=/tmp/.cache", env_values)
        self.assertIn("/tmp:rw,nosuid,nodev,size=512m", tmpfs_values)
        # A writable temporary home is needed by Semgrep builds that use /root directly.
        self.assertIn("/root:rw,nosuid,nodev,size=128m", tmpfs_values)
        self.assertNotIn("/root/.semgrep:rw,nosuid,nodev,size=16m", tmpfs_values)


if __name__ == "__main__":
    unittest.main()
