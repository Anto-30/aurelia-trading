from __future__ import annotations

import copy
import unittest

from scripts.validate_agent_inventory import validate_agent_remediation_backlog


KNOWN_AGENTS = {"ClaudeCode", "Dev"}


def make_fixture():
    backlog = {
        "schema": "aurelia.agent_remediation_backlog.v1",
        "canonical_repository": "https://github.com/Anto-30/aurelia-trading",
        "authority_model": {
            "constraints": [
                "external agents have no capital authority",
                "do not change LIVE_LOCK to force release",
                "no merge/deploy/promotion claim without observed platform result and required review",
            ],
            "continuous_operation_claim": "NOT_VERIFIED until persistent runtime evidence exists",
        },
        "status_legend": {
            "open": "identified work",
            "blocked": "external prerequisite",
            "verification_required": "evidence is required",
        },
        "workstreams": [
            {
                "id": "HOST-001",
                "priority": "P0",
                "status": "blocked",
                "title": "Register a persistent host",
                "finding": "No authorized host has been verified.",
                "owner": "Dev",
                "collaborators": ["ClaudeCode"],
                "dependencies": [],
                "external_prerequisites": ["explicit host authorization"],
                "acceptance_criteria": ["Verify authorized host identity."],
                "evidence_path": "artifacts/host.json",
            },
            {
                "id": "PROVIDER-002",
                "priority": "P0",
                "status": "blocked",
                "title": "Verify provider authentication",
                "finding": "Provider authentication is not verified.",
                "owner": "ClaudeCode",
                "collaborators": ["Dev"],
                "dependencies": ["HOST-001"],
                "external_prerequisites": [],
                "acceptance_criteria": ["Run an authenticated capability probe."],
                "evidence_path": "artifacts/provider.json",
            },
        ],
    }
    delegation = {
        "tasks": [
            {"agent": "Dev", "workstream_ids": ["HOST-001"]},
            {"agent": "ClaudeCode", "workstream_ids": ["PROVIDER-002"]},
        ]
    }
    return backlog, delegation


class AgentRemediationBacklogTests(unittest.TestCase):
    def test_valid_backlog_and_dependency_dag_pass(self):
        backlog, delegation = make_fixture()
        validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_missing_dependency_field_is_rejected(self):
        backlog, delegation = make_fixture()
        backlog["workstreams"][0].pop("dependencies")
        with self.assertRaisesRegex(AssertionError, "missing fields"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_dangling_dependency_id_is_rejected(self):
        backlog, delegation = make_fixture()
        backlog["workstreams"][1]["dependencies"] = ["UNKNOWN-999"]
        with self.assertRaisesRegex(AssertionError, "dangling dependency"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_dependency_cycle_is_rejected(self):
        backlog, delegation = make_fixture()
        backlog["workstreams"][0]["dependencies"] = ["PROVIDER-002"]
        with self.assertRaisesRegex(AssertionError, "dependency cycle"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_duplicate_workstream_ids_are_rejected(self):
        backlog, delegation = make_fixture()
        backlog["workstreams"][1]["id"] = "HOST-001"
        with self.assertRaisesRegex(AssertionError, "duplicate workstream id"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_unregistered_owner_or_collaborator_is_rejected(self):
        backlog, delegation = make_fixture()
        backlog["workstreams"][0]["owner"] = "Unregistered"
        with self.assertRaisesRegex(AssertionError, "owner"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)
        backlog, delegation = make_fixture()
        backlog["workstreams"][0]["collaborators"] = ["Unregistered"]
        with self.assertRaisesRegex(AssertionError, "collaborators"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_task_workstream_reference_must_exist(self):
        backlog, delegation = make_fixture()
        delegation["tasks"][0]["workstream_ids"] = ["MISSING-999"]
        with self.assertRaisesRegex(AssertionError, "unknown workstream id"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_orphan_workstream_is_rejected(self):
        backlog, delegation = make_fixture()
        delegation["tasks"][1]["workstream_ids"] = ["HOST-001"]
        with self.assertRaisesRegex(AssertionError, "duplicate delegation task agent|orphan workstreams"):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)

    def test_non_verified_continuous_operation_claim_is_rejected(self):
        backlog, delegation = make_fixture()
        backlog["authority_model"]["continuous_operation_claim"] = "RUNNING"
        with self.assertRaises(AssertionError):
            validate_agent_remediation_backlog(backlog, delegation, KNOWN_AGENTS)


if __name__ == "__main__":
    unittest.main()
