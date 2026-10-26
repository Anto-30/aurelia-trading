"""Regression tests for isolated external-candidate scanner configuration."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.audit_external_candidates import (
    audit_exit_code,
    docker_common_args,
    safe_tool_failure_class,
    semgrep_coverage_status,
    sanitize_semgrep,
    trivy_database_args,
    trivy_offline_scan_flags,
    prepare_trivy_databases,
    write_json_report,
)


class JsonReportSerializationTests(unittest.TestCase):
    def test_json_reports_are_strictly_parseable_and_end_with_a_real_newline(self):
        expected = {"status": "PARTIAL_BLOCKED", "message": "line one\nline two"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "semgrep_findings.json"
            write_json_report(output, expected)
            raw = output.read_bytes()

        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\\n"))
        self.assertEqual(json.loads(raw), expected)


class AuditExitCodeTests(unittest.TestCase):
    def test_clean_complete_scan_returns_zero(self):
        self.assertEqual(audit_exit_code(failed_scans=0, partial_scans=0), 0)

    def test_partial_coverage_fails_the_ci_gate(self):
        self.assertNotEqual(audit_exit_code(failed_scans=0, partial_scans=1), 0)

    def test_failed_scan_fails_the_ci_gate(self):
        self.assertNotEqual(audit_exit_code(failed_scans=1, partial_scans=0), 0)


class SemgrepCoverageTests(unittest.TestCase):
    def test_no_scanner_errors_is_complete(self):
        self.assertEqual(semgrep_coverage_status([]), "COMPLETED")

    def test_partial_parsing_warning_is_not_reported_complete(self):
        self.assertEqual(
            semgrep_coverage_status([{"level": "warn", "type": "PartialParsing", "code": 3}]),
            "PARTIAL_BLOCKED",
        )

    def test_scanner_timeout_is_not_reported_complete(self):
        self.assertEqual(
            semgrep_coverage_status([{"level": "warn", "type": "Timeout", "code": 2}]),
            "PARTIAL_BLOCKED",
        )

    def test_semgrep_severity_is_read_from_result_not_only_rule_metadata(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [{"check_id": "test-rule", "extra": {"severity": "ERROR", "metadata": {}}, "path": "x.py", "start": {"line": 1}, "end": {"line": 1}}],
            "errors": [],
        })
        self.assertEqual(report["severity_counts"], {"ERROR": 1})
        self.assertEqual(report["findings"][0]["severity"], "ERROR")

    def test_semgrep_severity_priority_and_fallback_are_counted_per_finding(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [
                {
                    "check_id": "error-rule",
                    "extra": {"severity": "ERROR", "metadata": {"severity": "INFO"}},
                    "path": "src/a.py",
                    "start": {"line": 1},
                    "end": {"line": 1},
                },
                {
                    "check_id": "fallback-rule",
                    "extra": {"metadata": {"severity": "WARNING"}},
                    "path": "src/b.py",
                    "start": {"line": 2},
                    "end": {"line": 2},
                },
            ],
            "errors": [],
        })
        self.assertEqual(report["severity_counts"], {"ERROR": 1, "WARNING": 1})
        self.assertEqual(report["findings_count"], 2)
        self.assertEqual(
            [finding["severity"] for finding in report["findings"]],
            ["ERROR", "WARNING"],
        )

    def test_semgrep_report_surfaces_coverage_limitation_without_raw_error_text(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [],
            "errors": [{
                "level": "warn",
                "code": 2,
                "type": "Timeout",
                "message": "sensitive raw diagnostic",
            }],
        })
        self.assertEqual(report["status"], "PARTIAL_BLOCKED")
        self.assertEqual(report["scanner_error_count"], 1)
        self.assertNotIn("sensitive raw diagnostic", str(report))

    def test_semgrep_error_type_counts_are_aggregated_without_raw_diagnostics(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [],
            "errors": [
                {
                    "level": "warn",
                    "code": 3,
                    "type": ["PartialParsing", [{"path": "/src/private/a.py", "line": 2}]],
                    "message": "private parser detail",
                },
                {
                    "level": "warn",
                    "code": 3,
                    "type": ["PartialParsing", [{"path": "/src/private/b.py", "line": 8}]],
                    "message": "another private parser detail",
                },
                {
                    "level": "warn",
                    "code": 2,
                    "type": "Timeout",
                    "message": "private timeout detail",
                },
            ],
        })
        self.assertEqual(
            report["scanner_error_type_counts"],
            [
                {"type": "PartialParsing", "code": 3, "level": "warn", "count": 2},
                {"type": "Timeout", "code": 2, "level": "warn", "count": 1},
            ],
        )
        serialized = json.dumps(report)
        self.assertNotIn("/src/private", serialized)
        self.assertNotIn("private parser detail", serialized)
        self.assertNotIn("private timeout detail", serialized)

    def test_semgrep_nested_error_type_does_not_leak_source_paths(self):
        report = sanitize_semgrep({
            "version": "test",
            "results": [],
            "errors": [{
                "level": "warn",
                "code": 3,
                "type": ["PartialParsing", [{"path": "/src/private/workflow.yml", "line": 4}]],
                "message": "raw parser message",
            }],
        })
        self.assertEqual(report["status"], "PARTIAL_BLOCKED")
        self.assertEqual(report["scanner_errors"][0]["type"], "PartialParsing")
        self.assertNotIn("/src/private/workflow.yml", json.dumps(report))
        self.assertNotIn("raw parser message", json.dumps(report))


class AuditDockerEnvironmentTests(unittest.TestCase):
    def test_trivy_scan_uses_only_cached_databases_and_rules(self):
        self.assertEqual(
            trivy_offline_scan_flags(),
            ["--skip-db-update", "--skip-java-db-update", "--skip-check-update"],
        )

    def test_scanner_network_mode_is_explicit_and_preflight_can_omit_candidate_mount(self):
        common = dict(
            image="aquasec/trivy:0.76.1",
            entrypoint="trivy",
            repo_dir=None,
            scratch_dir=Path("/tmp/aurelia-scan"),
            cache_dir=Path("/tmp/aurelia-cache"),
        )
        host_args = docker_common_args(**common, network="host")
        self.assertEqual(host_args[host_args.index("--network") + 1], "host")
        self.assertFalse(any("/src:ro" in arg for arg in host_args))
        offline_args = docker_common_args(**common, network="none")
        self.assertEqual(offline_args[offline_args.index("--network") + 1], "none")
        with self.assertRaisesRegex(ValueError, "INVALID_SCANNER_NETWORK_MODE"):
            docker_common_args(**common, network="invalid")

    def test_trivy_preflight_downloads_db_and_checks_without_candidate_source(self):
        from unittest.mock import patch
        from tools.audit_external_candidates import prepare_trivy_databases

        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            cache = Path(tmp) / "cache"
            cache.mkdir()
            observed_dockerfiles = []

            def capture_dockerfile(*_args, **_kwargs):
                dockerfile = scratch / "trivy-preflight-source" / "Dockerfile"
                if dockerfile.exists():
                    observed_dockerfiles.append(dockerfile.read_text(encoding="utf-8"))

            with patch("tools.audit_external_candidates.run_command") as run:
                run.side_effect = capture_dockerfile
                result = prepare_trivy_databases(
                    scratch, cache, "aquasec/trivy:0.76.1"
                )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(observed_dockerfiles, ["FROM scratch\n", "FROM scratch\n"])
        self.assertEqual(result["candidate_source_mounted"], False)
        self.assertEqual(result["java_db_policy"], "ON_DEMAND_FOR_JAR_CONTAINING_CANDIDATES")
        self.assertEqual(run.call_count, 2)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn("--download-db-only", commands[0])
        self.assertNotIn("--download-java-db-only", commands[0])
        self.assertEqual(commands[0][commands[0].index("--network") + 1], "host")
        self.assertEqual(commands[1][commands[1].index("--network") + 1], "host")
        self.assertFalse(any("/src:ro" in arg for arg in commands[0]))
        self.assertTrue(any("trivy-preflight-source" in arg for arg in commands[1]))
        self.assertLess(commands[0].index("image"), commands[0].index("--db-repository"))
        self.assertLess(commands[1].index("fs"), commands[1].index("--checks-bundle-repository"))

    def test_java_archive_detection_is_case_insensitive_and_deterministic(self):
        from tools.audit_external_candidates import find_java_archives
        self.assertEqual(
            find_java_archives(["a/one.jar", "b/TWO.JAR", "c/not-a-jar.txt", "a/one.jar"]),
            ["a/one.jar", "a/one.jar", "b/TWO.JAR"],
        )

    def test_java_db_preflight_is_targeted_and_does_not_mount_candidate_source(self):
        from unittest.mock import patch
        from tools.audit_external_candidates import prepare_trivy_java_database
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            cache = Path(tmp) / "cache"
            cache.mkdir()
            with patch("tools.audit_external_candidates.run_command") as run:
                result = prepare_trivy_java_database(scratch, cache, "aquasec/trivy:0.76.1")
        self.assertEqual(result["status"], "READY")
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertLess(command.index("image"), command.index("--java-db-repository"))
        self.assertIn("--download-java-db-only", command)
        self.assertEqual(command[command.index("--network") + 1], "host")
        self.assertFalse(any("/src:ro" in arg for arg in command))

    def test_trivy_skip_file_flags_are_repeated_for_each_unavailable_jar(self):
        skip_files = ["/src/a.jar", "/src/b.jar"]
        flags = [item for path in skip_files for item in ("--skip-files", path)]
        self.assertEqual(flags, ["--skip-files", "/src/a.jar", "--skip-files", "/src/b.jar"])

    def test_git_global_config_uses_writable_container_tmpfs(self):
        args = docker_common_args(
            "semgrep/semgrep:1.182.0",
            "semgrep",
            Path("/tmp/aurelia-source"),
            Path("/tmp/aurelia-scan"),
            Path("/tmp/aurelia-cache"),
        )
        env_values = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "-e"]
        tmpfs_values = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "--tmpfs"]

        user_index = args.index("--user")
        self.assertRegex(args[user_index + 1], r"^\d+:\d+$")
        self.assertIn("HOME=/tmp", env_values)
        self.assertIn("GIT_CONFIG_GLOBAL=/tmp/.gitconfig", env_values)
        self.assertIn("GIT_CONFIG_NOSYSTEM=1", env_values)
        self.assertIn("GIT_TERMINAL_PROMPT=0", env_values)
        self.assertIn("XDG_CONFIG_HOME=/tmp/.config", env_values)
        self.assertIn("XDG_CACHE_HOME=/tmp/.cache", env_values)
        self.assertIn("/tmp:rw,nosuid,nodev,size=512m", tmpfs_values)
        # A writable temporary home is needed by Semgrep builds that use /root directly.
        self.assertIn(
            f"/root:rw,nosuid,nodev,size=128m,uid={os.getuid()},gid={os.getgid()},mode=700",
            tmpfs_values,
        )
        self.assertNotIn("/root/.semgrep:rw,nosuid,nodev,size=16m", tmpfs_values)

    def test_trivy_database_fetch_failures_have_a_specific_safe_code(self):
        # Identify the security-database layer without exposing raw diagnostics.
        for diagnostic in (
            "failed to download vulnerability db: context deadline exceeded",
            "failed to fetch vulnerability database: remote registry unavailable",
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(
                    safe_tool_failure_class(diagnostic, ""),
                    "TRIVY_VULNERABILITY_DB_FETCH_FAILED",
                )

    def test_trivy_checks_bundle_fetch_failures_have_a_specific_safe_code(self):
        self.assertEqual(
            safe_tool_failure_class("failed to download checks bundle: registry request failed", ""),
            "TRIVY_CHECKS_BUNDLE_FETCH_FAILED",
        )

    def test_trivy_uses_official_vulnerability_database_fallbacks(self):
        args = trivy_database_args()
        repositories = [args[i + 1] for i, item in enumerate(args[:-1]) if item == "--db-repository"]
        self.assertEqual(
            repositories,
            [
                "mirror.gcr.io/aquasec/trivy-db",
                "ghcr.io/aquasecurity/trivy-db",
                "aquasec/trivy-db",
            ],
        )

    def test_trivy_uses_official_java_database_fallbacks_and_checks_bundle(self):
        args = trivy_database_args()
        java_repositories = [
            args[i + 1] for i, item in enumerate(args[:-1]) if item == "--java-db-repository"
        ]
        self.assertEqual(len(java_repositories), 3)
        self.assertEqual(
            java_repositories[0], "mirror.gcr.io/aquasec/trivy-java-db"
        )
        checks_index = args.index("--checks-bundle-repository")
        self.assertEqual(args[checks_index + 1], "mirror.gcr.io/aquasec/trivy-checks")


if __name__ == "__main__":
    unittest.main()
