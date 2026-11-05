from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MAIN_ONLY = "${{ github.ref == 'refs/heads/main' }}"


class PrivilegedWorkflowBranchGateTests(unittest.TestCase):
    def _job(self, filename: str, job_name: str) -> dict:
        workflow = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict, f"{filename} has no jobs mapping")
        job = jobs.get(job_name)
        self.assertIsInstance(job, dict, f"{filename} is missing job {job_name}")
        return job

    def test_production_secret_presence_job_is_main_only(self):
        job = self._job("secret-presence-report.yml", "report")
        self.assertEqual(job.get("if"), MAIN_ONLY)
        self.assertEqual(job.get("environment"), "production")

    def test_self_hosted_deployment_job_is_main_only_before_environment_secrets(self):
        job = self._job("self-hosted-runtime-deploy.yml", "deploy")
        self.assertEqual(job.get("if"), MAIN_ONLY)
        self.assertEqual(job.get("environment"), "production")

    def test_whatsapp_secret_job_is_main_only(self):
        job = self._job("aurelia-free-runtime.yml", "whatsapp-alert-smoke")
        self.assertEqual(job.get("if"), MAIN_ONLY)
        env = job.get("env", {})
        self.assertIn("TWILIO_ACCOUNT_SID", env)
        self.assertIn("TWILIO_AUTH_TOKEN", env)
        self.assertIn("TWILIO_API_SECRET", env)


    def _workflow_events(self, filename: str) -> dict:
        workflow = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
        # PyYAML's YAML 1.1 resolver parses the unquoted key "on" as True.
        events = workflow.get("on", workflow.get(True, {}))
        self.assertIsInstance(events, dict, f"{filename} has no workflow event mapping")
        return events

    def test_agent_federation_audit_runs_for_stacked_pull_requests(self):
        events = self._workflow_events("agent-federation-audit.yml")
        self.assertIn("pull_request", events)
        trigger = events["pull_request"]
        self.assertTrue(trigger is None or isinstance(trigger, dict))
        if isinstance(trigger, dict):
            self.assertNotIn("branches", trigger)

    def test_agent_continuity_watchdog_runs_for_stacked_pull_requests(self):
        events = self._workflow_events("agent-continuity-watchdog.yml")
        self.assertIn("pull_request", events)
        trigger = events["pull_request"]
        self.assertTrue(trigger is None or isinstance(trigger, dict))
        if isinstance(trigger, dict):
            self.assertNotIn("branches", trigger)

if __name__ == "__main__":
    unittest.main()
