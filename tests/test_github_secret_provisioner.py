from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = ROOT / "scripts" / "provision_deriv_github_secrets.sh"


class GitHubSecretProvisionerTest(unittest.TestCase):
    def test_provisioner_uses_stdin_and_never_prints_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            record = base / "written_secret_names.txt"
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
  "auth status")
    exit 0
    ;;
  "repo view")
    printf '%s\\n' 'Anto-30/aurelia-trading'
    ;;
  "api repos/Anto-30/aurelia-trading/environments/production")
    exit 0
    ;;
  "secret set")
    name="${3:?secret name missing}"
    value="$(cat)"
    test -n "$value"
    printf '%s\\n' "$name" >> "$PROVISIONER_TEST_RECORD"
    ;;
  "secret list")
    printf '%s\\n' \
      DERIV_AUTH_TOKEN \
      DERIV_APP_ID \
      DERIV_EXPECTED_LOGINID \
      DERIV_EXPECTED_CURRENCY \
      DERIV_AUTH_MODE
    ;;
  *)
    echo "unexpected gh command" >&2
    exit 9
    ;;
esac
""",
                encoding="utf-8",
            )
            fake_gh.chmod(0o700)
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                    "PROVISIONER_TEST_RECORD": str(record),
                    "DERIV_AUTH_MODE": "pat",
                    "DERIV_AUTH_TOKEN": "TEST_TOKEN_NEVER_PRINT",
                    "DERIV_APP_ID": "TEST_APP_ID_NEVER_PRINT",
                    "DERIV_EXPECTED_LOGINID": "TEST_LOGINID_NEVER_PRINT",
                    "DERIV_EXPECTED_CURRENCY": "USD",
                }
            )
            result = subprocess.run(
                ["bash", str(PROVISIONER)],
                check=False,
                text=True,
                capture_output=True,
                env=env,
                timeout=15,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DERIV_SECRET_PROVISIONING=COMPLETE", result.stdout)
            self.assertIn("SECRET_VALUES_PRINTED=false", result.stdout)
            for value in (
                "TEST_TOKEN_NEVER_PRINT",
                "TEST_APP_ID_NEVER_PRINT",
                "TEST_LOGINID_NEVER_PRINT",
            ):
                self.assertNotIn(value, result.stdout)
                self.assertNotIn(value, result.stderr)

            written_names = record.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                written_names,
                [
                    "DERIV_AUTH_TOKEN",
                    "DERIV_APP_ID",
                    "DERIV_EXPECTED_LOGINID",
                    "DERIV_EXPECTED_CURRENCY",
                    "DERIV_AUTH_MODE",
                ],
            )


if __name__ == "__main__":
    unittest.main()
