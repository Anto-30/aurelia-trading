from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_POLICY = (
    "Never enable Obscura's `--allow-private-network` flag or set "
    "`OBSCURA_ALLOW_PRIVATE_NETWORK=1` in the sandbox; both bypass the default denial "
    "for loopback, RFC1918, and link-local targets."
)


class ObscuraSandboxPolicyTests(unittest.TestCase):
    def test_private_network_bypass_is_explicitly_prohibited(self):
        for relative in (
            ".agents/skills/obscura-sandbox/SKILL.md",
            "docs/SECURITY_TOOLING_INTEGRATION.md",
        ):
            with self.subTest(path=relative):
                content = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(REQUIRED_POLICY, content)


if __name__ == "__main__":
    unittest.main()
