from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "claude-readonly-review.yml"
DOC = ROOT / "docs" / "agent-integration" / "claude-readonly-github-action.md"


class ClaudeReadOnlyReviewWorkflowTests(unittest.TestCase):
    def test_workflow_is_explicitly_opt_in_and_internal_pr_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", workflow)
        self.assertIn("!github.event.pull_request.draft", workflow)
        self.assertIn("vars.CLAUDE_REVIEW_ENABLED || 'false'", workflow)

    def test_github_permissions_are_read_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: read", workflow)
        self.assertIn("issues: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotRegex(
            workflow,
            re.compile(r"(?m)^\s*(?:contents|pull-requests|issues|actions):\s*write\s*$"),
        )
        self.assertIn("github_token: ${{ github.token }}", workflow)

    def test_actions_are_pinned_and_checkout_does_not_persist_token(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", workflow)
        self.assertIn("anthropics/claude-code-action@c0949c50a78c1ec8ce2647db36629b870e715d0c", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("fetch-depth: 0", workflow)

    def test_claude_has_only_read_search_tools_and_no_mcp_tools(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count('--tools "Read,Grep,Glob"'), 2)
        self.assertEqual(workflow.count('--disallowedTools "mcp__*"'), 2)
        self.assertEqual(workflow.count("--permission-mode plan"), 2)
        self.assertNotIn("--allowedTools", workflow)
        self.assertNotIn("show_full_output: \"true\"", workflow)
        self.assertIn("display_report: \"false\"", workflow)

    def test_credentials_are_gated_and_never_written_to_outputs(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", workflow)
        self.assertIn("ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}", workflow)
        self.assertIn("CLAUDE_READONLY_REVIEW=SKIPPED_CREDENTIAL_NOT_CONFIGURED", workflow)
        self.assertNotIn("echo \"$CLAUDE_CODE_OAUTH_TOKEN\"", workflow)
        self.assertNotIn("echo \"$ANTHROPIC_API_KEY\"", workflow)

    def test_prompt_forbids_repository_mutations_and_capital_actions(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for phrase in (
            "Do not edit files",
            "create branches or commits",
            "post comments",
            "access secrets or broker/account data",
            "change LIVE_LOCK",
            "submit trading orders",
        ):
            self.assertEqual(workflow.count(phrase), 2, phrase)

    def test_documentation_explains_owner_setup_and_disabled_default(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("CLAUDE_REVIEW_ENABLED=true", doc)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", doc)
        self.assertIn("ANTHROPIC_API_KEY", doc)
        self.assertIn("disabled by default", doc.lower())
        self.assertIn("cannot configure protected Actions secrets", doc)


if __name__ == "__main__":
    unittest.main()
