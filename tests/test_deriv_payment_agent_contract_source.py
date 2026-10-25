from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "deriv-payment-agent.openapi.yaml"


def section(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at + len(start))
    return source[start_at:end_at]


class DerivPaymentAgentContractSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_upstream_snapshot_is_pinned_without_claiming_live_identity(self) -> None:
        pin = section(self.contract, "x-aurelia-upstream-source:", "\ntags:")
        self.assertIn("release_tag: production_v20260901_0", pin)
        self.assertIn("git_commit: 54e353807146d31f58291693243cbbf671de7bce", pin)
        self.assertIn("source_blob_sha: b785658de90b1c8010629f90b81c9441fa119f74", pin)
        self.assertIn(
            "sha256: 8a2655d9b9713f65296035ba02f8cf6f281ab95fcf454dd996b763a53506682f",
            pin,
        )
        self.assertIn("content_bytes: 241565", pin)
        self.assertIn("content_bytes: 241565", pin)
        self.assertIn("direct_live_endpoint_identity_verified: false", pin)

    def test_directory_list_matches_the_pinned_official_array_contract(self) -> None:
        list_route = section(
            self.contract, "  /payment-agents/v1/agents:\n",
            "  /payment-agents/v1/agents/{id}:"
        )
        list_item = section(
            self.contract, "    PaymentAgentListItem:", "    DirectoryEnvelope:"
        )
        directory = self.contract[self.contract.index("    DirectoryEnvelope:") :]

        self.assertIn("required: true", list_route)
        self.assertIn(
            "pattern: '^[A-Z_]{1,18}$'",
            section(self.contract, "    Currency:", "    Amount:"),
        )
        self.assertIn("default: 1", list_route)
        self.assertIn("default: 25", list_route)
        self.assertIn("'400': { $ref: '#/components/responses/BadRequest' }", list_route)
        self.assertIn("schema: { $ref: '#/components/schemas/DirectoryEnvelope' }", list_route)
        self.assertIn("required: [data, errors, metadata]", directory)
        self.assertIn("type: array", directory)
        self.assertIn(
            "items: { $ref: '#/components/schemas/PaymentAgentListItem' }", directory
        )
        self.assertNotIn("oneOf:", directory)
        self.assertIn("required: [id]", list_item)
        self.assertIn("deposit_commission: { type: [number, 'null'] }", list_item)
        self.assertIn("withdrawal_minimum: { type: [string, 'null'] }", list_item)

    def test_agent_id_and_standard_error_envelope_match_official_shape(self) -> None:
        agent_route = section(
            self.contract, "  /payment-agents/v1/agents/{id}:",
            "  /payment-agents/v1/clients/me:"
        )
        error = section(self.contract, "    ApiError:", "    ErrorEnvelope:")
        envelope = section(self.contract, "    ErrorEnvelope:", "    StatisticsEnvelope:")

        self.assertIn("pattern: '^(?:[1-9]\\d*|me)$'", agent_route)
        self.assertIn("required: [status, code]", error)
        self.assertNotRegex(error, r"(?m)^ {8}message:")
        self.assertIn("detail:", error)
        self.assertIn("required: [data, errors, metadata]", envelope)

    def test_security_scheme_matches_official_payment_scope(self) -> None:
        security_scheme = section(
            self.contract, "  securitySchemes:", "  parameters:"
        )
        self.assertIn("- oauth2: [payment]", self.contract)
        self.assertIn("type: oauth2", security_scheme)
        self.assertIn("authorizationUrl: https://oauth.deriv.com/oauth2/authorize", security_scheme)
        self.assertIn("tokenUrl: https://oauth.deriv.com/oauth2/token", security_scheme)
        self.assertIn("payment: Access to payment agent deposit and withdrawal operations", security_scheme)
        self.assertNotIn("BearerAuth", self.contract)
        self.assertNotIn("DerivAppId", self.contract)
        self.assertNotIn("PAT also requires Deriv-App-ID", self.contract)

    def test_contract_keeps_all_external_side_effects_deny_by_default(self) -> None:
        for expected in (
            "defaultMode: TEST_ONLY",
            "liveMoneyWritesPermitted: false",
            "fakeTransportRequiredForTests: true",
            "verificationCodeDispatchPermitted: false",
            "clientPrivacyMutationsPermitted: false",
            "neverBlindlyResubmitAmbiguousWrite: true",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.contract)


if __name__ == "__main__":
    unittest.main()
