from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = ROOT / "scripts" / "provision_deriv_github_secrets.sh"


FAKE_GH = """#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
  "auth status")
    exit 0
    ;;
  "repo view")
    printf '%s\n' 'Anto-30/aurelia-trading'
    ;;
  "api repos/Anto-30/aurelia-trading/environments/production")
    exit 0
    ;;
  "secret set")
    name="${3:?secret name missing}"
    value="$(cat)"
    test -n "$value"
    printf '%s\n' "$name" >> "$PROVISIONER_TEST_RECORD"
    ;;
  "secret list")
    {
      printf '%s\n' "${PROVISIONER_TEST_EXISTING_NAMES:-}" | grep -v '^$' || true
      if [[ -f "$PROVISIONER_TEST_RECORD" ]]; then
        cat "$PROVISIONER_TEST_RECORD"
      fi
    } | sort -u
    ;;
  "variable set")
    name="${3:?variable name missing}"
    value="$(cat)"
    test -n "$value"
    printf '%s\n' "$name" >> "$PROVISIONER_TEST_VARIABLE_RECORD"
    ;;
  "variable list")
    {
      printf '%s\n' "${PROVISIONER_TEST_EXISTING_VARIABLE_NAMES:-}" | grep -v '^$' || true
      if [[ -f "$PROVISIONER_TEST_VARIABLE_RECORD" ]]; then
        cat "$PROVISIONER_TEST_VARIABLE_RECORD"
      fi
    } | sort -u
    ;;
  *)
    echo "unexpected gh command" >&2
    exit 9
    ;;
esac
"""


class GitHubSecretProvisionerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.bin_dir = self.base / "bin"
        self.bin_dir.mkdir()
        self.record = self.base / "written_secret_names.txt"
        self.variable_record = self.base / "written_variable_names.txt"
        fake_gh = self.bin_dir / "gh"
        fake_gh.write_text(FAKE_GH, encoding="utf-8")
        fake_gh.chmod(0o700)
        self.env = dict(os.environ)
        self.env.update(
            {
                "PATH": f"{self.bin_dir}{os.pathsep}{self.env.get('PATH', '')}",
                "PROVISIONER_TEST_RECORD": str(self.record),
                "PROVISIONER_TEST_VARIABLE_RECORD": str(self.variable_record),
                "DERIV_AUTH_MODE": "pat",
                "DERIV_AUTH_TOKEN": "TEST_TOKEN_NEVER_PRINT",
                "DERIV_APP_ID": "TEST_APP_ID_NEVER_PRINT",
                "DERIV_EXPECTED_LOGINID": "TEST_LOGINID_NEVER_PRINT",
                "DERIV_EXPECTED_CURRENCY": "USD",
                "PROVISIONER_TEST_EXISTING_NAMES": "",
                "PROVISIONER_TEST_EXISTING_VARIABLE_NAMES": "",
            }
        )

    def run_provisioner(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PROVISIONER)],
            check=False,
            text=True,
            capture_output=True,
            env=self.env,
            timeout=15,
        )

    def test_missing_secrets_are_added_without_printing_values(self) -> None:
        result = self.run_provisioner()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DERIV_SECRET_PROVISIONING=COMPLETE", result.stdout)
        self.assertIn("SECRET_VALUES_PRINTED=false", result.stdout)
        self.assertIn("EXISTING_SECRET_VALUES_OVERWRITTEN=false", result.stdout)
        for value in (
            "TEST_TOKEN_NEVER_PRINT",
            "TEST_APP_ID_NEVER_PRINT",
            "TEST_LOGINID_NEVER_PRINT",
        ):
            self.assertNotIn(value, result.stdout)
            self.assertNotIn(value, result.stderr)

        written_names = self.record.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            written_names,
            [
                "DERIV_AUTH_TOKEN",
                "DERIV_APP_ID",
                "DERIV_EXPECTED_LOGINID",
                "DERIV_EXPECTED_CURRENCY",
            ],
        )
        self.assertEqual(
            self.variable_record.read_text(encoding="utf-8").splitlines(),
            ["DERIV_AUTH_MODE"],
        )

    def test_existing_secrets_and_variables_are_not_overwritten(self) -> None:
        self.env["PROVISIONER_TEST_EXISTING_NAMES"] = "\n".join(
            [
                "DERIV_PAT",
                "DERIV_APP_ID",
                "DERIV_EXPECTED_LOGINID",
                "DERIV_EXPECTED_CURRENCY",
            ]
        )
        self.env["PROVISIONER_TEST_EXISTING_VARIABLE_NAMES"] = "DERIV_AUTH_MODE"
        self.env.pop("DERIV_AUTH_TOKEN", None)
        self.env.pop("DERIV_PAT", None)
        self.env.pop("DERIV_APP_ID", None)
        self.env.pop("DERIV_EXPECTED_LOGINID", None)
        self.env.pop("DERIV_EXPECTED_CURRENCY", None)

        result = self.run_provisioner()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DERIV_SECRET_PROVISIONING=COMPLETE", result.stdout)
        self.assertIn("EXISTING_SECRET_VALUES_OVERWRITTEN=false", result.stdout)
        self.assertFalse(self.record.exists(), "existing GitHub secrets must not be written over")
        self.assertFalse(self.variable_record.exists(), "existing GitHub variables must not be written over")
        self.assertNotIn("TEST_TOKEN_NEVER_PRINT", result.stdout)
        self.assertNotIn("TEST_TOKEN_NEVER_PRINT", result.stderr)


if __name__ == "__main__":
    unittest.main()
