import json
import unittest
from pathlib import Path

from runtime.core.capability_authorizer import CapabilityAuthorizer, CapabilityRequest


class CapabilityAuthorizerTests(unittest.TestCase):
    def setUp(self):
        boundary = json.loads(
            Path("config/agent_capability_boundary.json").read_text(encoding="utf-8")
        )
        self.auth = CapabilityAuthorizer(boundary)

    def test_unknown_actor_denied(self):
        result = self.auth.authorize(
            CapabilityRequest("unknown", "research", "NONE", "research")
        )
        self.assertFalse(result.allowed)

    def test_capital_capability_always_denied(self):
        result = self.auth.authorize(
            CapabilityRequest("Grok", "submit_order", "ORDER_SUBMISSION", "real")
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "CAPITAL_CAPABILITY_FORBIDDEN_AT_AGENT_BOUNDARY")

    def test_allowed_research_capability(self):
        result = self.auth.authorize(
            CapabilityRequest("Grok", "research", "NONE", "research")
        )
        self.assertTrue(result.allowed)

    def test_real_capital_side_effect_denied(self):
        result = self.auth.authorize(
            CapabilityRequest("ClaudeCode", "modify_code", "CAPITAL", "real")
        )
        self.assertFalse(result.allowed)

    def test_secret_scope_denied(self):
        result = self.auth.authorize(
            CapabilityRequest("ClaudeCode", "inspect", "NONE", "research", "PRIVATE_SECRET")
        )
        self.assertFalse(result.allowed)
