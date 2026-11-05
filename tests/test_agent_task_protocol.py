from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.agents.task_protocol import (
    ProtocolError,
    decode_message,
    persist_evidence,
    validate_hello,
    validate_task_result,
)


class TestAgentTaskProtocol(unittest.TestCase):
    def test_decode_message_requires_a_json_object(self):
        with self.assertRaisesRegex(ProtocolError, "MESSAGE_NOT_OBJECT"):
            decode_message(b'["not", "an", "object"]\n')

    def test_decode_message_rejects_oversized_input(self):
        with self.assertRaisesRegex(ProtocolError, "MESSAGE_TOO_LARGE"):
            decode_message(b'{"x":"' + b"a" * 128 + b'"}\n', max_bytes=64)

    def test_validate_hello_requires_protocol_and_exact_agent_identity(self):
        good = {"type": "HELLO", "protocol_version": 1, "agent": "ClaudeCode"}
        validate_hello(good, expected_agent="ClaudeCode")

        with self.assertRaisesRegex(ProtocolError, "WORKER_IDENTITY_MISMATCH"):
            validate_hello(good, expected_agent="DeepSeekHarness")

    def test_task_result_requires_exact_task_and_claim_token(self):
        result = {
            "type": "TASK_RESULT",
            "protocol_version": 1,
            "agent": "ClaudeCode",
            "task_id": "task:123",
            "claim_token": "one-time-secret",
            "status": "COMPLETED",
            "result": {"summary": "review complete"},
            "evidence": {"kind": "review", "findings": []},
        }
        accepted = validate_task_result(
            result,
            expected_agent="ClaudeCode",
            expected_task_id="task:123",
            expected_claim_token="one-time-secret",
        )
        self.assertEqual(accepted.status, "COMPLETED")
        self.assertEqual(accepted.result, {"summary": "review complete"})

        with self.assertRaisesRegex(ProtocolError, "TASK_ID_MISMATCH"):
            validate_task_result(
                result,
                expected_agent="ClaudeCode",
                expected_task_id="task:other",
                expected_claim_token="one-time-secret",
            )

        with self.assertRaisesRegex(ProtocolError, "CLAIM_TOKEN_MISMATCH"):
            validate_task_result(
                result,
                expected_agent="ClaudeCode",
                expected_task_id="task:123",
                expected_claim_token="wrong-token",
            )

    def test_task_result_rejects_claims_of_capital_authority(self):
        result = {
            "type": "TASK_RESULT",
            "protocol_version": 1,
            "agent": "ClaudeCode",
            "task_id": "task:123",
            "claim_token": "one-time-secret",
            "status": "COMPLETED",
            "result": {"capital_authority": True},
            "evidence": {"kind": "review", "findings": []},
        }
        with self.assertRaisesRegex(ProtocolError, "CAPITAL_AUTHORITY_CLAIM_FORBIDDEN"):
            validate_task_result(
                result,
                expected_agent="ClaudeCode",
                expected_task_id="task:123",
                expected_claim_token="one-time-secret",
            )

    def test_completed_task_requires_nonempty_evidence(self):
        result = {
            "type": "TASK_RESULT",
            "protocol_version": 1,
            "agent": "ClaudeCode",
            "task_id": "task:123",
            "claim_token": "one-time-secret",
            "status": "COMPLETED",
            "result": {"summary": "done"},
            "evidence": {},
        }
        with self.assertRaisesRegex(ProtocolError, "TASK_EVIDENCE_REQUIRED"):
            validate_task_result(
                result,
                expected_agent="ClaudeCode",
                expected_task_id="task:123",
                expected_claim_token="one-time-secret",
            )


    def test_task_result_rejects_secret_capability_fields_inside_evidence(self):
        result = {
            "type": "TASK_RESULT",
            "protocol_version": 1,
            "agent": "ClaudeCode",
            "task_id": "task:123",
            "claim_token": "one-time-secret",
            "status": "COMPLETED",
            "result": {"summary": "done"},
            "evidence": {"claim_token": "should-not-be-persisted"},
        }
        with self.assertRaisesRegex(ProtocolError, "SECRET_FIELD_FORBIDDEN"):
            validate_task_result(
                result,
                expected_agent="ClaudeCode",
                expected_task_id="task:123",
                expected_claim_token="one-time-secret",
            )

    def test_persisted_evidence_is_content_addressed_and_verifiable(self):
        with tempfile.TemporaryDirectory(prefix="aurelia-protocol-test-") as tmp:
            root = Path(tmp)
            record = {"schema": "aurelia.agent_task_evidence.v1", "task_id": "task:123"}
            artifact = persist_evidence(root, record)
            raw = (root / artifact.relative_ref).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), artifact.sha256)
            self.assertEqual(json.loads(raw), record)
            self.assertTrue(artifact.relative_ref.startswith("agent-tasks/"))


class TestAgentTaskFederationProtocol(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="aurelia-federation-test-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        from runtime.agent_federation import PersistentAgentFederation

        self.federation = PersistentAgentFederation(
            journal_path=self.root / "journal.ndjson",
            lease_path=self.root / "leases.json",
            task_path=self.root / "tasks.json",
            config_hash="cfg",
            source_hash="src",
            lease_seconds=5,
        )

    async def test_federation_claim_requires_bound_worker_capability(self):
        enqueued = await self.federation.enqueue_task(
            task_type="ENGINEERING_REVIEW",
            payload={"scope": "safe"},
            correlation_id="claim-capability",
            assigned_agent="ClaudeCode",
        )
        claim = await self.federation.claim_task("ClaudeCode", worker_id="worker-1")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.task_id, enqueued.task_id)
        self.assertTrue(claim.claim_token)

        self.assertFalse(await self.federation.complete_task(
            claim.task_id,
            agent="ClaudeCode",
            worker_id="worker-1",
            claim_token="incorrect-capability",
            status="COMPLETED",
        ))
        self.assertTrue(await self.federation.renew_task_claim(
            claim.task_id,
            agent="ClaudeCode",
            worker_id="worker-1",
            claim_token=claim.claim_token,
        ))
        self.assertTrue(await self.federation.complete_task(
            claim.task_id,
            agent="ClaudeCode",
            worker_id="worker-1",
            claim_token=claim.claim_token,
            status="COMPLETED",
            evidence_ref="agent-tasks/test.json",
            result={"verified": False},
        ))

    async def test_supervisor_executes_and_records_attributable_jsonl_result(self):
        from runtime.agent_workers import AgentWorkerSupervisor

        worker_script = r'''
import json
import sys

print(json.dumps({
    "type": "HELLO",
    "protocol_version": 1,
    "agent": "ClaudeCode"
}), flush=True)

for raw in sys.stdin:
    message = json.loads(raw)
    if message.get("type") != "TASK":
        continue
    response = {
        "type": "TASK_RESULT",
        "protocol_version": 1,
        "agent": "ClaudeCode",
        "task_id": message["task_id"],
        "claim_token": message["claim_token"],
        "status": "COMPLETED",
        "result": {"summary": "worker completed task", "verified": True},
        "evidence": {"kind": "test-report", "checks": ["one", "two"]}
    }
    print(json.dumps(response, separators=(",", ":")), flush=True)
'''
        command = f"{shlex.quote(sys.executable)} -u -c {shlex.quote(worker_script)}"
        await self.federation.enqueue_task(
            task_type="ENGINEERING_REVIEW",
            payload={"scope": "protocol integration test"},
            correlation_id="worker-protocol-integration",
            assigned_agent="ClaudeCode",
        )
        supervisor = AgentWorkerSupervisor(
            self.federation,
            agents=("ClaudeCode",),
            interval_seconds=0.05,
            startup_timeout_seconds=2,
            task_timeout_seconds=2,
            evidence_root=self.root,
        )
        stored = []
        with patch.dict(os.environ, {"AURELIA_AGENT_CLAUDECODE_COMMAND": command}):
            supervisor.start()
            deadline = time.monotonic() + 4
            try:
                while time.monotonic() < deadline:
                    stored = self.federation._load_tasks()
                    if stored and stored[0].get("status") in {"COMPLETED", "FAILED", "BLOCKED"}:
                        break
                    await asyncio.sleep(0.05)
            finally:
                await supervisor.stop()

        self.assertEqual(stored[0]["status"], "COMPLETED")
        self.assertTrue(
            stored[0]["completed_by_worker_id"].startswith("agent-worker:ClaudeCode:")
        )
        evidence_path = self.root / stored[0]["evidence_ref"]
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertTrue(evidence["attribution"]["claim_capability_validated"])
        self.assertFalse(evidence["attribution"]["provider_authentication"])
        self.assertTrue(evidence["worker_result"]["verified"])
        # The worker's self-asserted verification flag is never promoted into
        # the deterministic assurance fields consumed by the ledger.
        self.assertFalse(stored[0]["result"]["verified"])
