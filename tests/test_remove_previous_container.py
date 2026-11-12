from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "deploy" / "remove_previous_container.sh"


class RemovePreviousContainerTests(unittest.TestCase):
    def run_helper(self, *, info_fail="0", container_exists="0", remove_fail="0"):
        with tempfile.TemporaryDirectory(prefix="aurelia-docker-fake-") as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            log_path = root / "sudo.log"
            sudo = fake_bin / "sudo"
            sudo.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$FAKE_SUDO_LOG"
case "$*" in
  "docker info")
    [[ "$FAKE_DOCKER_INFO_FAIL" != "1" ]]
    ;;
  "docker ps --all --quiet --filter name=^/aurelia-runtime$")
    if [[ "$FAKE_CONTAINER_EXISTS" == "1" ]]; then
      printf '%s\n' "container-id-123"
    fi
    ;;
  "docker rm -f container-id-123")
    [[ "$FAKE_DOCKER_RM_FAIL" != "1" ]]
    ;;
  *)
    echo "UNEXPECTED_FAKE_COMMAND=$*" >&2
    exit 91
    ;;
esac
""",
                encoding="utf-8",
            )
            sudo.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
                    "FAKE_SUDO_LOG": str(log_path),
                    "FAKE_DOCKER_INFO_FAIL": info_fail,
                    "FAKE_CONTAINER_EXISTS": container_exists,
                    "FAKE_DOCKER_RM_FAIL": remove_fail,
                }
            )
            result = subprocess.run(
                ["bash", str(HELPER), "aurelia-runtime"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=5,
            )
            log = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
            return result, log

    def test_absent_container_is_a_safe_noop(self):
        result, log = self.run_helper(container_exists="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            log,
            [
                "docker info",
                "docker ps --all --quiet --filter name=^/aurelia-runtime$",
            ],
        )

    def test_existing_container_is_removed_by_id(self):
        result, log = self.run_helper(container_exists="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            log,
            [
                "docker info",
                "docker ps --all --quiet --filter name=^/aurelia-runtime$",
                "docker rm -f container-id-123",
            ],
        )

    def test_daemon_failure_aborts_before_listing_or_removal(self):
        result, log = self.run_helper(info_fail="1", container_exists="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log, ["docker info"])

    def test_container_removal_failure_is_propagated(self):
        result, log = self.run_helper(container_exists="1", remove_fail="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            log,
            [
                "docker info",
                "docker ps --all --quiet --filter name=^/aurelia-runtime$",
                "docker rm -f container-id-123",
            ],
        )

    def test_invalid_container_name_is_rejected_before_docker(self):
        result = subprocess.run(
            ["bash", str(HELPER), "../aurelia-runtime"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID_CONTAINER_NAME", result.stdout)


if __name__ == "__main__":
    unittest.main()
