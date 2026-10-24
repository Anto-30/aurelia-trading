from __future__ import annotations

import copy
import subprocess
import sys
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
    def test_validators_refuse_optimized_python_mode(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        for script in (
            "scripts/validate_agent_inventory.py",
            "scripts/validate_agent_tool_skill_assignments.py",
        ):
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, "-O", str(root / script)],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=15,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "Refusing optimized Python mode: validator assertions would be disabled",
                    result.stderr + result.stdout,
                )


    def test_disconnected_agent_with_blocked_task_is_valid(self):
        validate_persistent_agent_routing(*fixtures())

    def test_disconnected_agent_cannot_be_marked_assigned(self):
        routing, profiles, delegation = fixtures()
        delegation["tasks"][0]["status"] = "assigned"
        with self.assertRaisesRegex(AssertionError, "runtime is not connected"):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_unverified_runtime_cannot_be_marked_assigned(self):
        routing, profiles, delegation = fixtures()
        routing["agents"]["DeepSeekHarness"]["runtime_status"] = (
            "EXTERNAL_RUNTIME_NOT_VERIFIED_BY_THIS_CHAT"
        )
        delegation["tasks"][0]["status"] = "assigned"
        with self.assertRaisesRegex(AssertionError, "runtime is not connected"):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_shadow_only_runtime_cannot_be_marked_assigned(self):
        routing, profiles, delegation = fixtures()
        routing["agents"]["DeepSeekHarness"]["runtime_status"] = (
            "REGISTERED_SHADOW_ONLY"
        )
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

    def test_every_registered_agent_must_have_exactly_one_task(self):
        routing, profiles, delegation = fixtures()
        profiles["ClaudeCode"] = {
            "can_mutate_live_lock": False,
            "capital_authority": False,
        }
        with self.assertRaisesRegex(AssertionError, "missing=\\['ClaudeCode'\\]"):
            validate_persistent_agent_routing(routing, profiles, delegation)

    def test_unregistered_agent_cannot_own_a_task(self):
        routing, profiles, delegation = fixtures()
        unexpected = copy.deepcopy(delegation["tasks"][0])
        unexpected["task_id"] = "AGT-UNKNOWN-001"
        unexpected["agent"] = "GhostAgent"
        delegation["tasks"].append(unexpected)
        with self.assertRaisesRegex(AssertionError, "unknown=\\['GhostAgent'\\]"):
            validate_persistent_agent_routing(routing, profiles, delegation)


if __name__ == "__main__":
    unittest.main()
