from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = ROOT / "scripts" / "provision_deriv_github_secrets.sh"


class GitHubSecretProvisionerTest(unittest.TestCase):
    def test_provisioner_blocks_without_invoking_github_cli_or_echoing_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            marker = "PAT_SECRET_MUST_NOT_APPEAR"
            fake_gh = Path(td) / "gh"
            called = Path(td) / "gh_was_called"
            fake_gh.write_text(
                "#!/bin/sh\ntouch \"$GH_CALLED_MARKER\"\nexit 0\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o700)
            env = dict(os.environ)
            env.update({
                "PATH": f"{td}{os.pathsep}{env.get('PATH', '')}",
                "GH_CALLED_MARKER": str(called),
                "DERIV_AUTH_TOKEN": marker,
                "DERIV_PAT": marker,
                "DERIV_OAUTH_ACCESS_TOKEN": marker,
            })
            result = subprocess.run(
                ["bash", str(PROVISIONER)],
                check=False,
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", result.stderr)
            self.assertFalse(called.exists())
            self.assertNotIn(marker, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
