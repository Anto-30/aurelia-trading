import unittest
from unittest.mock import Mock

from runtime.payment.transport_guard import (
    GuardedPaymentAgentTransport,
    PaymentPolicyError,
)


class PaymentAgentTransportGuardTests(unittest.TestCase):
    def setUp(self):
        self.raw_transport = Mock()
        self.raw_transport.request.return_value = {"fixture": True}

    def test_test_only_denies_network_before_transport(self):
        client = GuardedPaymentAgentTransport(
            self.raw_transport,
            capital_plane_mode="VERIFY_ONLY",
            transport_mode="TEST_ONLY",
        )
        with self.assertRaisesRegex(PaymentPolicyError, "PAYMENT_TRANSPORT_NOT_AUTHENTICATED_VERIFY_ONLY"):
            client.request("GET", "/payment-agents/v1/agent-statistics")
        self.raw_transport.request.assert_not_called()

    def test_non_verify_only_mode_denies_authenticated_rest_before_transport(self):
        for mode in (None, "", "BLOCKED", "TEST_ONLY", "LIVE"):
            with self.subTest(mode=mode):
                raw = Mock()
                client = GuardedPaymentAgentTransport(
                    raw,
                    capital_plane_mode=mode,
                    transport_mode="AUTHENTICATED_VERIFY_ONLY",
                )
                with self.assertRaisesRegex(PaymentPolicyError, "CAPITAL_PLANE_MODE_NOT_VERIFY_ONLY"):
                    client.request("GET", "/payment-agents/v1/agent-statistics")
                raw.request.assert_not_called()

    def test_verify_only_allows_allowlisted_read(self):
        client = GuardedPaymentAgentTransport(
            self.raw_transport,
            capital_plane_mode="VERIFY_ONLY",
            transport_mode="AUTHENTICATED_VERIFY_ONLY",
        )
        result = client.request("GET", "/payment-agents/v1/agent-statistics", timeout=2)
        self.assertEqual(result, {"fixture": True})
        self.raw_transport.request.assert_called_once_with(
            "GET", "/payment-agents/v1/agent-statistics", timeout=2
        )

    def test_all_payment_writes_are_denied_even_in_verify_only(self):
        paths = (
            "/payment-agents/v1/clients/me",
            "/payment-agents/v1/transfer",
            "/payment-agents/v1/withdraw/verification_code",
            "/payment-agents/v1/withdraw",
        )
        for path in paths:
            with self.subTest(path=path):
                raw = Mock()
                client = GuardedPaymentAgentTransport(
                    raw,
                    capital_plane_mode="VERIFY_ONLY",
                    transport_mode="AUTHENTICATED_VERIFY_ONLY",
                )
                with self.assertRaisesRegex(PaymentPolicyError, "PAYMENT_WRITE_DISABLED"):
                    client.request("POST" if path != "/payment-agents/v1/clients/me" else "PATCH", path)
                raw.request.assert_not_called()

    def test_only_status_gets_are_allowed_for_transfer_and_withdraw(self):
        client = GuardedPaymentAgentTransport(
            self.raw_transport,
            capital_plane_mode="VERIFY_ONLY",
            transport_mode="AUTHENTICATED_VERIFY_ONLY",
        )
        for path in (
            "/payment-agents/v1/transfer/req_123",
            "/payment-agents/v1/withdraw/req-456",
        ):
            with self.subTest(path=path):
                client.request("GET", path)
        self.assertEqual(self.raw_transport.request.call_count, 2)

    def test_exact_agent_profile_routes_are_allowed(self):
        client = GuardedPaymentAgentTransport(
            self.raw_transport,
            capital_plane_mode="VERIFY_ONLY",
            transport_mode="AUTHENTICATED_VERIFY_ONLY",
        )
        client.request("GET", "/payment-agents/v1/agents/me")
        client.request("GET", "/payment-agents/v1/agents/123")
        self.assertEqual(self.raw_transport.request.call_count, 2)

    def test_nested_traversal_and_normalized_paths_are_denied(self):
        paths = (
            "/payment-agents/v1/agents/../transfer/req_123",
            "/payment-agents/v1/agents/7/transfer/req_123",
            "/payment-agents/v1/agents/%2e%2e/transfer/req_123",
            "/payment-agents/v1/transfer/req_123?expand=true",
            "/payment-agents/v1/transfer/req_123#fragment",
            "/payment-agents/v1/withdraw/verification_code/123",
            "https://api.derivws.com/payment-agents/v1/agents/123",
            "//api.derivws.com/payment-agents/v1/agents/123",
        )
        for path in paths:
            with self.subTest(path=path):
                raw = Mock()
                client = GuardedPaymentAgentTransport(
                    raw,
                    capital_plane_mode="VERIFY_ONLY",
                    transport_mode="AUTHENTICATED_VERIFY_ONLY",
                )
                with self.assertRaisesRegex(
                    PaymentPolicyError, "PAYMENT_ENDPOINT_NOT_ALLOWLISTED"
                ):
                    client.request("GET", path)
                raw.request.assert_not_called()

    def test_write_like_or_unknown_paths_are_denied(self):
        paths = (
            "/payment-agents/v1/transfer/",
            "/payment-agents/v1/withdraw/verification_code",
            "/payment-agents/v1/agents/not-a-numeric-id",
            "/trading/v1/options/contracts/bulk-purchase/real",
        )
        for path in paths:
            with self.subTest(path=path):
                raw = Mock()
                client = GuardedPaymentAgentTransport(
                    raw,
                    capital_plane_mode="VERIFY_ONLY",
                    transport_mode="AUTHENTICATED_VERIFY_ONLY",
                )
                with self.assertRaises(PaymentPolicyError):
                    client.request("GET", path)
                raw.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
