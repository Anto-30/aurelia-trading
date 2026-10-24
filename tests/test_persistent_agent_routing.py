from __future__ import annotations

import copy
import unittest

from scripts.validate_agent_tool_skill_assignments import validate_persistent_agent_routing


def fixtures():
    routing = {
        "schema": "aurelia.persistent_agent_plugin_routing.v1",
        "guarantee_boundary": {
            "repository_policy_persists": True,
            "runtime_plugin_installation_or_authentication_guaranteed_by_registry": False,
            "automatic_external_provider_connection_from_chatgpt": False,
            "report_unavailable_capability_as": "BLOCKED_NOT_CONNECTED",
            "never_claim_connection_without": [
                "provider/runtime identity",
                "successful authenticated capability probe",
                "timestamped evidence",
                "permission scope",
            ],
        },
        "task_start_contract": ["Verify a runtime before delegation."],
        "agents": {
            "DeepSeekHarness": {
                "role": "independent read-only review",
                "intended_plugins": ["GitHub read", "CI logs/artifacts read-only"],
                "runtime_status": "REGISTERED_SHADOW_ONLY_NOT_CONNECTED",
                "persistence_status": "NOT_PROVEN",
                "activation_rule": "Keep blocked until an authenticated capability probe succeeds.",
            }
        },
        "governance": {
            "live_execution": "BLOCKED",
            "final_execution_authorization": False,
            "live_lock_mutation_by_external_agents": False,
            "external_agents_capital_authority": False,
        },
    }
    profiles = {
        "DeepSeekHarness": {
            "can_mutate_live_lock": False,
            "capital_authority": False,
        }
    }
    delegation = {
        "tasks": [
            {
                "task_id": "AGT-DEEPSEEK-001",
                "agent": "DeepSeekHarness",
                "status": "blocked",
                "blocked_reason": "No authenticated model/runtime connection has been verified.",
                "unblock_evidence_required": ["Authenticated capability probe"],
                "runtime_proof": {"execution_proof": False},
            }
        ]
    }
    return routing, profiles, delegation


class PersistentAgentRoutingTests(unittest.TestCase):
    def test_disconnected_agent_with_blocked_task_is_valid(self):
        validate_persistent_agent_routing(*fixtures())

    def test_disconnected_agent_cannot_be_marked_assigned(self):
        routing, profiles, delegation = fixtures()
        delegation["tasks"][0]["status"] = "assigned"
        with self.assertRaisesRegex(AssertionError, "runtime is not connected"):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_external_agent_cannot_gain_capital_authority(self):
        routing, profiles, delegation = fixtures()
        routing["governance"]["external_agents_capital_authority"] = True
        with self.assertRaises(AssertionError):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_routing_cannot_reference_unknown_agent(self):
        routing, profiles, delegation = fixtures()
        routing["agents"]["UnknownAgent"] = copy.deepcopy(routing["agents"]["DeepSeekHarness"])
        with self.assertRaisesRegex(AssertionError, "unknown agent profiles"):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_disconnected_task_requires_reason_and_unblock_evidence(self):
        routing, profiles, delegation = fixtures()
        delegation["tasks"][0].pop("unblock_evidence_required")
        with self.assertRaises(AssertionError):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_duplicate_delegation_owner_is_rejected(self):
        routing, profiles, delegation = fixtures()
        duplicate = copy.deepcopy(delegation["tasks"][0])
        duplicate["task_id"] = "AGT-DEEPSEEK-002"
        delegation["tasks"].append(duplicate)
        with self.assertRaisesRegex(AssertionError, "duplicate or missing delegation task owner"):
            validate_persistent_agent_routing(routing, profiles, delegation)


if __name__ == "__main__":
    unittest.main()
