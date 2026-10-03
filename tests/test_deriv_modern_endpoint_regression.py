from __future__ import annotations

import unittest
from pathlib import Path

from runtime.adapters.deriv_session import (
    DerivSessionError,
    validate_modern_options_ws_url,
)


ROOT = Path(__file__).resolve().parents[1]


class ModernDerivEndpointRegressionTests(unittest.TestCase):
    def test_modern_real_endpoint_is_accepted(self) -> None:
        self.assertTrue(
            validate_modern_options_ws_url(
                "wss://api.derivws.com/trading/v1/options/ws/real"
            )
        )

    def test_legacy_endpoint_is_rejected(self) -> None:
        with self.assertRaises(DerivSessionError):
            validate_modern_options_ws_url(
                "wss://ws.derivws.com/websockets/v3"
            )

    def test_executable_production_code_contains_no_legacy_deriv_host(self) -> None:
        executable_roots = (
            ROOT / "runtime",
            ROOT / "execution",
            ROOT / "capital",
        )
        offenders: list[str] = []
        legacy_markers = (
            "ws.derivws.com",
            "binaryws.derivws.com",
            "websockets/v3",
        )
        for base in executable_roots:
            if not base.exists():
                continue
            for path in base.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if any(marker in text for marker in legacy_markers):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual([], offenders, f"legacy Deriv endpoint in executable code: {offenders}")


if __name__ == "__main__":
    unittest.main()
