#!/usr/bin/env python3
"""Audit pinned external repositories without installing or executing candidate code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SEMGREP_IMAGE = "semgrep/semgrep:1.182.0"
DEFAULT_TRIVY_IMAGE = "aquasec/trivy:0.76.1"
TRIVY_DB_REPOSITORIES = (
    "mirror.gcr.io/aquasec/trivy-db",
    "ghcr.io/aquasecurity/trivy-db",
    "aquasec/trivy-db",
)
TRIVY_JAVA_DB_REPOSITORIES = (
    "mirror.gcr.io/aquasec/trivy-java-db",
    "ghcr.io/aquasecurity/trivy-java-db",
    "aquasec/trivy-java-db",
)
TRIVY_CHECKS_BUNDLE_REPOSITORY = "mirror.gcr.io/aquasec/trivy-checks"
SAFE_ENV_KEYS = {
    "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
    "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
}
LOCKFILE_NAMES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock",
    "bun.lockb", "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock",
    "go.sum", "composer.lock", "Gemfile.lock", "pom.xml",
    "gradle.lockfile", "packages.lock.json", "npm-shrinkwrap.json",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile",
    "Cargo.toml", "go.mod", "composer.json", "Gemfile", "pom.xml",
    "build.gradle", "build.gradle.kts", "Directory.Build.props",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_env() -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if key in SAFE_ENV_KEYS}
    result["GIT_CONFIG_NOSYSTEM"] = "1"
    result["GIT_CONFIG_GLOBAL"] = os.devnull
    result["GIT_TERMINAL_PROMPT"] = "0"
    result["GIT_LFS_SKIP_SMUDGE"] = "1"
    result["GIT_OPTIONAL_LOCKS"] = "0"
    return result


def safe_tool_failure_class(stderr: str, stdout: str) -> str:
    text = ((stderr or "") + "\\n" + (stdout or "")).lower()
    patterns = [
        (("failed to download vulnerability db", "failed to download vulnerability database",
          "unable to download vulnerability db", "failed to fetch vulnerability db",
          "failed to fetch the vulnerability database", "failed to fetch vulnerability database"),
         "TRIVY_VULNERABILITY_DB_FETCH_FAILED"),
        (("failed to download checks bundle", "unable to download checks bundle",
          "checks bundle download failed"), "TRIVY_CHECKS_BUNDLE_FETCH_FAILED"),
        (("failed to download java db", "failed to download Java DB",
          "unable to download java db", "failed to fetch java db",
          "failed to fetch the java database", "failed to fetch java database"),
         "TRIVY_JAVA_DB_FETCH_FAILED"),
        (("no such option", "unrecognized option", "unknown option"), "CLI_OPTION_ERROR"),
        (("usage:", "invalid choice", "unrecognized arguments"), "CLI_ARGUMENT_ERROR"),
        (("could not resolve", "failed to fetch", "failed to download", "connection refused",
          "temporary failure in name resolution", "certificate verify failed", "http error"),
         "NETWORK_OR_RULESET_FETCH_ERROR"),
        (("permission denied", "read-only file system", "operation not permitted"),
         "SANDBOX_FILESYSTEM_ERROR"),
        (("no such file or directory", "executable file not found", "not found"),
         "EXECUTABLE_OR_PATH_ERROR"),
        (("invalid configuration", "could not find config", "could not resolve config",
          "failed to load config", "no config found"), "RULESET_CONFIGURATION_ERROR"),
        (("semgrep-core", "internal error", "traceback"), "SCANNER_RUNTIME_ERROR"),
    ]
    for needles, code in patterns:
        if any(needle in text for needle in needles):
            return code
    return "SCANNER_NONZERO_EXIT"


def run_command(
    command: list[str],
    *,
    timeout: int = 900,
    cwd: Path | None = None,
    allowed_codes: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=safe_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if process.returncode not in allowed_codes:
        # Only print narrowly allowlisted CLI parser diagnostics. Never print raw stderr/stdout,
        # which may contain source excerpts, findings, or detected secret values.
        safe_patterns = (
            r"(?:No such option|unrecognized option|unknown option)[: ]+['\"]?[-A-Za-z0-9_]+['\"]?",
            r"unrecognized arguments?: --[A-Za-z0-9_-]+",
            r"No such command '[A-Za-z0-9_-]+'",
            r"unknown command [A-Za-z0-9_-]+",
            r"executable file not found in \\$PATH",
        )
        for text_blob in (process.stderr, process.stdout):
            for pattern in safe_patterns:
                match = re.search(pattern, text_blob or "", flags=re.IGNORECASE)
                if match:
                    print("SAFE_TOOL_CLI_HINT=" + match.group(0)[:160])
                    break
        failure_class = safe_tool_failure_class(process.stderr, process.stdout)
        print("SAFE_TOOL_FAILURE_CLASS=" + failure_class)
        failure = RuntimeError(
            "COMMAND_FAILED:"
            + Path(command[0]).name
            + ":exit="
            + str(process.returncode)
        )
        # Keep the full failure detail private while allowing the preflight report
        # to record a safe, machine-readable reason.
        setattr(failure, "safe_tool_failure_class", failure_class)
        raise failure
    return process


def safe_relative(path_value: Any) -> str:
    value = str(path_value or "")
    for prefix in ("/src/", "src/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value[:1000]


def docker_image_digests(image: str) -> dict[str, Any]:
    try:
        proc = run_command(
            ["docker", "image", "inspect", "--format={{json .RepoDigests}}", image],
            timeout=30,
        )
        values = json.loads(proc.stdout.strip() or "[]")
        ident = run_command(
            ["docker", "image", "inspect", "--format={{.Id}}", image],
            timeout=30,
        ).stdout.strip()
        return {"image": image, "image_id": ident, "repo_digests": values}
    except Exception as exc:
        return {"image": image, "inspection_status": "BLOCKED", "error_type": type(exc).__name__}


def git_fetch_candidate(candidate: dict[str, Any], clone_dir: Path) -> dict[str, Any]:
    repo = str(candidate["repository"])
    sha = str(candidate["commit_sha"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("INVALID_REPOSITORY_IDENTIFIER")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("INVALID_COMMIT_SHA")

    clone_dir.mkdir(parents=True, exist_ok=False)
    run_command(["git", "init", "--quiet", str(clone_dir)], timeout=30)
    run_command(
        ["git", "-C", str(clone_dir), "remote", "add", "origin", "https://github.com/" + repo + ".git"],
        timeout=30,
    )
    # Fetch only the exact pinned commit; no checkout hooks, submodules, LFS smudge,
    # package installation, build scripts or tests are executed.
    branch = str(candidate.get("default_branch") or "")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or ".." in branch:
        raise ValueError("INVALID_DEFAULT_BRANCH")

    fetch_method = "direct-pinned-sha"
    try:
        run_command(
            ["git", "-C", str(clone_dir), "fetch", "--quiet", "--filter=blob:none",
             "--depth=1", "origin", sha],
            timeout=300,
        )
        checkout_target = "FETCH_HEAD"
    except Exception:
        # Some servers reject a SHA-only want even when it is reachable. Fetch only the
        # public default-branch history since 2026-01-01 (all manifest pins are newer),
        # without blobs, then check out the exact SHA. Never check out HEAD as a substitute.
        fetch_method = "default-branch-history-fallback"
        run_command(
            ["git", "-C", str(clone_dir), "fetch", "--quiet", "--filter=blob:none",
             "--shallow-since=2026-01-01T00:00:00Z", "origin", "refs/heads/" + branch],
            timeout=900,
        )
        checkout_target = sha
        exists = run_command(
            ["git", "-C", str(clone_dir), "cat-file", "-e", sha + "^{commit}"],
            timeout=30,
        )
    run_command(
        ["git", "-C", str(clone_dir), "-c", "core.hooksPath=" + os.devnull,
         "checkout", "--quiet", "--detach", checkout_target],
        timeout=180,
    )
    actual = run_command(
        ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
        timeout=30,
    ).stdout.strip()
    if actual != sha:
        raise RuntimeError("PIN_MISMATCH")

    tree = run_command(
        ["git", "-C", str(clone_dir), "ls-tree", "-r", "--name-only", "HEAD"],
        timeout=120,
    ).stdout.splitlines()
    root_names = {name for name in tree if "/" not in name}
    manifests = sorted(
        name for name in tree
        if Path(name).name in MANIFEST_NAMES
        or Path(name).name in LOCKFILE_NAMES
        or re.fullmatch(r"requirements[^/]*\.txt", Path(name).name, re.I)
        or Path(name).name.endswith((".csproj", ".fsproj", ".vbproj"))
    )
    lockfiles = sorted(
        name for name in tree
        if Path(name).name in LOCKFILE_NAMES
        or re.fullmatch(r"requirements[^/]*\.txt", Path(name).name, re.I)
    )
    licenses = sorted(
        name for name in tree
        if "/" not in name
        and re.match(r"^(LICENSE|LICENCE|COPYING)([._-].*)?$", name, re.I)
    )
    submodules = run_command(
        ["git", "-C", str(clone_dir), "ls-tree", "-r", "HEAD"],
        timeout=120,
    ).stdout.splitlines()
    submodule_count = sum(1 for line in submodules if line.startswith("160000 "))

    return {
        "repository": repo,
        "requested_commit_sha": sha,
        "checked_out_commit_sha": actual,
        "fetch_method": fetch_method,
        "pin_verified": True,
        "file_count": len(tree),
        "root_file_names": sorted(root_names)[:500],
        "root_license_file_names": licenses,
        "dependency_manifest_paths": manifests[:2000],
        "dependency_lockfile_paths": lockfiles[:2000],
        "submodule_entry_count_not_initialized": submodule_count,
        "candidate_scripts_executed": False,
        "candidate_dependencies_installed": False,
        "candidate_builds_run": False,
        "candidate_tests_run": False,
    }


def docker_common_args(
    image: str,
    entrypoint: str,
    repo_dir: Path | None,
    scratch_dir: Path,
    cache_dir: Path,
    *,
    network: str = "bridge",
) -> list[str]:
    if network not in {"bridge", "host", "none"}:
        raise ValueError("INVALID_SCANNER_NETWORK_MODE")
    args = [
        "docker", "run", "--rm",
        "--network", network,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp",
        "-e", "GIT_CONFIG_GLOBAL=/tmp/.gitconfig",
        "-e", "GIT_CONFIG_NOSYSTEM=1",
        "-e", "GIT_TERMINAL_PROMPT=0",
        "-e", "XDG_CONFIG_HOME=/tmp/.config",
        "-e", "XDG_CACHE_HOME=/tmp/.cache",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=512",
        "--memory=4g",
        "--entrypoint", entrypoint,
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
        # Some scanner builds resolve user state through /root despite HOME/GIT_CONFIG overrides.
        # Only ephemeral scanner state is writable; scanner image and candidate source stay read-only.
        "--tmpfs", f"/root:rw,nosuid,nodev,size=128m,uid={os.getuid()},gid={os.getgid()},mode=700",
    ]
    if repo_dir is not None:
        args.extend(["-v", str(repo_dir.resolve()) + ":/src:ro"])
    args.extend([
        "-v", str(scratch_dir.resolve()) + ":/scan:rw",
        "-v", str(cache_dir.resolve()) + ":/root/.cache:rw",
        image,
    ])
    return args

def trivy_database_args() -> list[str]:
    """Use ordered official registry mirrors with fallback rather than a single default registry."""
    args: list[str] = []
    for repository in TRIVY_DB_REPOSITORIES:
        args.extend(["--db-repository", repository])
    for repository in TRIVY_JAVA_DB_REPOSITORIES:
        args.extend(["--java-db-repository", repository])
    # Trivy accepts a single checks-bundle registry. The GCR mirror is configured explicitly;
    # the pinned scanner binary also carries an embedded fallback bundle.
    args.extend(["--checks-bundle-repository", TRIVY_CHECKS_BUNDLE_REPOSITORY])
    return args



def trivy_offline_scan_flags() -> list[str]:
    """Require cached databases and prevent candidate scans from opening network access."""
    return ["--skip-db-update", "--skip-java-db-update", "--skip-check-update"]


def prepare_trivy_databases(
    scratch_dir: Path, cache_dir: Path, image: str
) -> dict[str, Any]:
    """Populate trusted Trivy databases before a candidate source is mounted."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    empty_source = scratch_dir / "trivy-preflight-source"
    empty_source.mkdir(parents=True, exist_ok=True)
    (empty_source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    preflight_report = scratch_dir / "trivy-preflight.json"
    try:
        downloaded: list[str] = []
        for flag, label, repositories, repository_flag in (
            ("--download-db-only", "vulnerability_database", TRIVY_DB_REPOSITORIES, "--db-repository"),
            ("--download-java-db-only", "java_database", TRIVY_JAVA_DB_REPOSITORIES, "--java-db-repository"),
        ):
            database_args = [
                item
                for repository in repositories
                for item in (repository_flag, repository)
            ]
            # Database options are scoped to the image subcommand; keep this preflight source-free.
            command = docker_common_args(
                image, "trivy", None, scratch_dir, cache_dir, network="host"
            ) + [
                "image",
                *database_args,
                "--cache-dir", "/root/.cache/trivy",
                flag,
            ]
            run_command(command, timeout=900)
            downloaded.append(label)

        # Trigger the checks-bundle path once against a locally generated empty fixture.
        # No external candidate source is mounted, parsed, or executed in this host-network phase.
        command = docker_common_args(
            image, "trivy", empty_source, scratch_dir, cache_dir, network="host"
        ) + [
            "fs",
            *trivy_database_args(),
            "--cache-dir", "/root/.cache/trivy",
            "--scanners", "misconfig",
            "--format", "json", "--output", "/scan/trivy-preflight.json", "/src",
        ]
        run_command(command, timeout=300)
        return {
            "status": "READY",
            "databases_downloaded": downloaded,
            "checks_preflight": "COMPLETED",
            "candidate_source_mounted": False,
        }
    finally:
        if preflight_report.exists():
            preflight_report.unlink()
        shutil.rmtree(empty_source, ignore_errors=True)


def semgrep_coverage_status(errors: list[Any]) -> str:
    """Do not label a partial Semgrep analysis complete."""
    return "COMPLETED" if not errors else "PARTIAL_BLOCKED"


def audit_exit_code(*, failed_scans: int, partial_scans: int) -> int:
    """Return success only when all candidate scans complete without coverage errors."""
    return 0 if failed_scans == 0 and partial_scans == 0 else 2


def safe_semgrep_error_type(error: Any) -> str:
    """Keep scanner error classifications scalar; Semgrep may nest source paths in its type field."""
    if not isinstance(error, dict):
        return "UNKNOWN"
    raw_type = error.get("type")
    if isinstance(raw_type, str):
        return raw_type[:120]
    if isinstance(raw_type, list):
        # PartialParsing and some parser diagnostics include nested source ranges and paths.
        # Retain only the top-level label and never serialize nested structures.
        for value in raw_type:
            if isinstance(value, str):
                return value[:120]
        return "UNKNOWN"
    return "UNKNOWN"


def sanitize_semgrep(raw_report: dict[str, Any]) -> dict[str, Any]:
    safe_findings = []
    severity_counts: Counter[str] = Counter()
    for item in raw_report.get("results") or []:
        extra = item.get("extra") or {}
        metadata = extra.get("metadata") or {}
        # Semgrep's JSON result severity is on `extra.severity`; rule metadata may not duplicate it.
        severity = str(extra.get("severity") or metadata.get("severity") or "UNKNOWN").upper()
        severity_counts[severity] += 1
        safe_findings.append({
            "rule_id": str(item.get("check_id") or "UNKNOWN")[:500],
            "severity": severity,
            "path": safe_relative(item.get("path")),
            "start_line": (item.get("start") or {}).get("line"),
            "end_line": (item.get("end") or {}).get("line"),
            "cwe": metadata.get("cwe") if isinstance(metadata.get("cwe"), (str, list)) else None,
            "owasp": metadata.get("owasp") if isinstance(metadata.get("owasp"), (str, list)) else None,
            "confidence": metadata.get("confidence"),
        })
    safe_findings.sort(key=lambda x: (x["severity"], x["path"], x["start_line"] or 0, x["rule_id"]))
    errors = raw_report.get("errors") or []
    coverage_status = semgrep_coverage_status(errors)
    return {
        "status": coverage_status,
        "coverage_status": coverage_status,
        "ruleset_names": ["p/default", "p/secrets"],
        "scanner_version": raw_report.get("version"),
        "findings_count": len(safe_findings),
        "severity_counts": dict(sorted(severity_counts.items())),
        "findings": safe_findings[:10000],
        "findings_truncated": len(safe_findings) > 10000,
        "scanner_error_count": len(errors),
        # Raw error messages are omitted to prevent source excerpts or sensitive data leaking.
        "scanner_errors": [
            {
                "type": safe_semgrep_error_type(error),
                "code": (error.get("code") if isinstance(error, dict) else None),
                "level": (error.get("level") if isinstance(error, dict) else None),
            }
            for error in errors[:200]
        ],
    }


def sanitize_trivy(raw_report: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    findings: list[dict[str, Any]] = []
    results = raw_report.get("Results") or []

    for result in results:
        target = safe_relative(result.get("Target"))
        for vuln in result.get("Vulnerabilities") or []:
            severity = str(vuln.get("Severity") or "UNKNOWN").upper()
            counts["vulnerability"] += 1
            severity_counts[severity] += 1
            findings.append({
                "kind": "vulnerability",
                "id": str(vuln.get("VulnerabilityID") or "UNKNOWN")[:200],
                "package": str(vuln.get("PkgName") or "")[:300],
                "installed_version": str(vuln.get("InstalledVersion") or "")[:100],
                "fixed_version": str(vuln.get("FixedVersion") or "")[:200],
                "severity": severity,
                "path": target,
                "url": str(vuln.get("PrimaryURL") or "")[:1000],
            })

        for item in result.get("Misconfigurations") or []:
            severity = str(item.get("Severity") or "UNKNOWN").upper()
            counts["misconfiguration"] += 1
            severity_counts[severity] += 1
            meta = item.get("CauseMetadata") or {}
            findings.append({
                "kind": "misconfiguration",
                "id": str(item.get("ID") or "UNKNOWN")[:200],
                "title": str(item.get("Title") or "")[:300],
                "severity": severity,
                "path": safe_relative(meta.get("Resource") or target),
                "start_line": meta.get("StartLine"),
                "end_line": meta.get("EndLine"),
                "type": str(item.get("Type") or "")[:100],
            })

        for secret in result.get("Secrets") or []:
            severity = str(secret.get("Severity") or "UNKNOWN").upper()
            counts["secret"] += 1
            severity_counts[severity] += 1
            # Intentionally omit Match, Code, Raw, Title, Description and any secret material.
            findings.append({
                "kind": "secret",
                "id": str(secret.get("RuleID") or "UNKNOWN")[:200],
                "category": str(secret.get("Category") or "")[:100],
                "severity": severity,
                "path": target,
                "start_line": secret.get("StartLine"),
                "end_line": secret.get("EndLine"),
            })

        for license_item in result.get("Licenses") or []:
            severity = str(license_item.get("Severity") or "UNKNOWN").upper()
            counts["license"] += 1
            severity_counts[severity] += 1
            findings.append({
                "kind": "license",
                "id": str(license_item.get("Name") or license_item.get("PkgName") or "UNKNOWN")[:300],
                "package": str(license_item.get("PkgName") or "")[:300],
                "severity": severity,
                "path": safe_relative(license_item.get("FilePath") or target),
                "confidence": license_item.get("Confidence"),
            })

    findings.sort(key=lambda x: (
        x.get("kind", ""), x.get("severity", ""),
        x.get("path", ""), x.get("start_line") or 0, x.get("id", "")
    ))
    return {
        "status": "COMPLETED",
        "scanner_version": raw_report.get("SchemaVersion"),
        "finding_counts_by_kind": dict(sorted(counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "findings_count": len(findings),
        "findings": findings[:20000],
        "findings_truncated": len(findings) > 20000,
        "raw_report_errors_not_disclosed": True,
    }


def run_semgrep(
    repo_dir: Path, scratch_dir: Path, cache_dir: Path, image: str
) -> dict[str, Any]:
    raw_path = scratch_dir / "semgrep.raw.json"
    command = docker_common_args(image, "semgrep", repo_dir, scratch_dir, cache_dir) + [
        "scan",
        "--config", "p/default", "--config", "p/secrets",
        "--metrics=off", "--json",
        "--output", "/scan/semgrep.raw.json",
        "--exclude", ".git", "/src",
    ]
    try:
        # Semgrep exits 1 when findings are present and 0 when none are found.
        # Exit 2 and any other code remain hard scan failures.
        proc = run_command(command, timeout=1200, allowed_codes=(0, 1))
        if not raw_path.is_file():
            raise RuntimeError("SEMGREP_REPORT_MISSING")
        report = json.loads(raw_path.read_text(encoding="utf-8"))
        sanitized = sanitize_semgrep(report)
        sanitized["process_exit_code"] = proc.returncode
        sanitized["report_sha256"] = sha256_file(raw_path)
        return sanitized
    finally:
        if raw_path.exists():
            raw_path.unlink()


def run_trivy(
    repo_dir: Path, candidate_out: Path, scratch_dir: Path,
    cache_dir: Path, image: str
) -> dict[str, Any]:
    raw_path = scratch_dir / "trivy.raw.json"
    sbom_path = candidate_out / "sbom.cdx.json"
    command = docker_common_args(image, "trivy", repo_dir, scratch_dir, cache_dir, network="none") + [
        "fs", *trivy_database_args(), "--cache-dir", "/root/.cache/trivy",
        "--scanners", "vuln,misconfig,secret,license",
        *trivy_offline_scan_flags(),
        "--format", "json", "--output", "/scan/trivy.raw.json", "/src",
    ]
    try:
        proc = run_command(command, timeout=1200, allowed_codes=(0,))
        if not raw_path.is_file():
            raise RuntimeError("TRIVY_REPORT_MISSING")
        report = json.loads(raw_path.read_text(encoding="utf-8"))
        sanitized = sanitize_trivy(report)
        sanitized["process_exit_code"] = proc.returncode
        sanitized["report_sha256"] = sha256_file(raw_path)
    finally:
        if raw_path.exists():
            raw_path.unlink()

    # Write an SBOM containing package/license metadata; do not include the secret scan output.
    sbom_command = docker_common_args(image, "trivy", repo_dir, scratch_dir, cache_dir, network="none") + [
        "fs", *trivy_database_args(), "--cache-dir", "/root/.cache/trivy",
        "--scanners", "vuln,license",
        *trivy_offline_scan_flags(),
        "--format", "cyclonedx", "--output", "/scan/sbom.cdx.json", "/src",
    ]
    scratch_sbom = scratch_dir / "sbom.cdx.json"
    try:
        run_command(sbom_command, timeout=1200, allowed_codes=(0,))
        if not scratch_sbom.is_file():
            raise RuntimeError("TRIVY_SBOM_MISSING")
        shutil.copyfile(scratch_sbom, sbom_path)
        sanitized["sbom_path"] = str(sbom_path.name)
        sanitized["sbom_sha256"] = sha256_file(sbom_path)
        sanitized["sbom_status"] = "GENERATED"
    finally:
        if scratch_sbom.exists():
            scratch_sbom.unlink()
    return sanitized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/tmp/aurelia-external-audit"))
    parser.add_argument("--semgrep-image", default=DEFAULT_SEMGREP_IMAGE)
    parser.add_argument("--trivy-image", default=DEFAULT_TRIVY_IMAGE)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 24:
        print("AUDIT_RESULT=BLOCKED")
        print("AUDIT_REASON=EXPECTED_24_PINNED_CANDIDATES")
        return 2
    names = [candidate.get("repository") for candidate in candidates]
    if len(set(names)) != len(names):
        print("AUDIT_RESULT=BLOCKED")
        print("AUDIT_REASON=DUPLICATE_REPOSITORIES")
        return 2
    for candidate in candidates:
        if candidate.get("intake_status") not in {"UNREVIEWED", "BLOCKED"}:
            print("AUDIT_RESULT=BLOCKED")
            print("AUDIT_REASON=CANDIDATE_NOT_UNREVIEWED")
            return 2
        if not re.fullmatch(r"[0-9a-f]{40}", str(candidate.get("commit_sha") or "")):
            print("AUDIT_RESULT=BLOCKED")
            print("AUDIT_REASON=INVALID_PIN")
            return 2

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        print("AUDIT_RESULT=BLOCKED")
        print("AUDIT_REASON=OUTPUT_DIR_NOT_EMPTY")
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.scratch_dir / "docker-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    tool_images = {
        "semgrep": docker_image_digests(args.semgrep_image),
        "trivy": docker_image_digests(args.trivy_image),
    }
    try:
        trivy_preflight = prepare_trivy_databases(args.scratch_dir, cache_dir, args.trivy_image)
        print("TRIVY_PREFLIGHT=READY")
    except Exception as exc:
        # Do not multiply a shared database/registry outage across all candidate scans.
        message = str(exc)
        error_code = getattr(exc, "safe_tool_failure_class", None)
        if not isinstance(error_code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}", error_code):
            error_code = message if re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}", message) else "TRIVY_PREFLIGHT_FAILED"
        print("AUDIT_RESULT=BLOCKED")
        print("AUDIT_REASON=TRIVY_DATABASE_PREFLIGHT_FAILED")
        print("AUDIT_ERROR_CODE=" + error_code)
        preflight_report = {
            "schema": "aurelia.external_candidate_audit_report.v1",
            "status": "AUDIT_PREFLIGHT_BLOCKED",
            "review_status": "HUMAN_REVIEW_REQUIRED",
            "promotion_approved": False,
            "created_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "source_manifest_sha256": sha256_file(args.manifest),
            "candidate_count": len(candidates),
            "candidate_scans_complete": 0,
            "candidate_scans_blocked": len(candidates),
            "candidate_scans_partial": 0,
            "preflight": {
                "status": "BLOCKED",
                "stage": "trivy_database_and_checks",
                "safe_error_code": error_code,
                "candidate_code_executed": False,
                "candidate_dependencies_installed": False,
            },
            "tool_images": tool_images,
            "execution_policy": {
                "candidate_dependencies_installed": False,
                "candidate_code_executed": False,
                "candidate_builds_run": False,
                "candidate_tests_run": False,
                "git_submodules_initialized": False,
                "raw_scanner_reports_uploaded": False,
                "secret_values_in_reports": False,
            },
            "candidates": [],
        }
        (args.output_dir / "audit-summary.json").write_text(
            json.dumps(preflight_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.output_dir / "audit-summary.md").write_text(
            "# External Candidate Static Audit Summary\n\n"
            "Status: AUDIT_PREFLIGHT_BLOCKED\n\n"
            "The trusted Trivy database/check preflight could not complete. "
            "No candidate source scan was started; no clean scan is claimed.\n",
            encoding="utf-8",
        )
        return 2
    results: list[dict[str, Any]] = []
    started_at = utc_now()
    failed_scans = 0
    partial_scans = 0

    for index, candidate in enumerate(candidates, start=1):
        repository = candidate["repository"]
        audit_id = repository.replace("/", "--")
        candidate_out = args.output_dir / audit_id
        candidate_out.mkdir(parents=True, exist_ok=False)
        clone_dir = args.scratch_dir / ("source-" + audit_id)
        scratch_dir = args.scratch_dir / ("scan-" + audit_id)
        scratch_dir.mkdir(parents=True, exist_ok=False)

        print("CANDIDATE_START=" + repository)
        status = "SCAN_COMPLETE_HUMAN_REVIEW_REQUIRED"
        result: dict[str, Any] = {
            "repository": repository,
            "source_url": candidate["source_url"],
            "commit_sha": candidate["commit_sha"],
            "default_branch": candidate.get("default_branch"),
            "expected_license": candidate.get("expected_license"),
            "scope_note": candidate.get("scope_note"),
            "intake_status": candidate.get("intake_status"),
            "promotion_approved": False,
            "review_status": "HUMAN_REVIEW_REQUIRED",
            "candidate_code_executed": False,
            "candidate_dependencies_installed": False,
            "candidate_build_or_tests_run": False,
            "started_at_utc": utc_now(),
            "scanner_status": {},
            "finding_counts": {},
            "report_files": {},
        }

        phase = "source_checkout"
        try:
            metadata = git_fetch_candidate(candidate, clone_dir)
            result["source_metadata"] = metadata
            phase = "semgrep"
            semgrep_report = run_semgrep(clone_dir, scratch_dir, cache_dir, args.semgrep_image)
            semgrep_out = candidate_out / "semgrep_findings.json"
            semgrep_out.write_text(
                json.dumps(semgrep_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            phase = "trivy"
            trivy_report = run_trivy(
                clone_dir, candidate_out, scratch_dir, cache_dir, args.trivy_image
            )
            trivy_out = candidate_out / "trivy_findings.json"
            trivy_out.write_text(
                json.dumps(trivy_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            result["scanner_status"] = {
                "semgrep": semgrep_report["status"],
                "semgrep_error_count": semgrep_report["scanner_error_count"],
                "trivy": "COMPLETED",
            }
            result["finding_counts"] = {
                "semgrep": semgrep_report["findings_count"],
                "semgrep_scanner_errors": semgrep_report["scanner_error_count"],
                "trivy_total": trivy_report["findings_count"],
                "trivy_by_kind": trivy_report["finding_counts_by_kind"],
                "trivy_by_severity": trivy_report["severity_counts"],
            }
            result["report_files"] = {
                "semgrep_findings": semgrep_out.name,
                "semgrep_findings_sha256": sha256_file(semgrep_out),
                "trivy_findings": trivy_out.name,
                "trivy_findings_sha256": sha256_file(trivy_out),
                "sbom": "sbom.cdx.json",
                "sbom_sha256": sha256_file(candidate_out / "sbom.cdx.json"),
            }
            if semgrep_report["status"] != "COMPLETED":
                # Keep the useful Trivy/Semgrep reports, but explicitly prevent false full-coverage claims.
                status = "SCAN_COMPLETE_WITH_COVERAGE_LIMITATIONS_HUMAN_REVIEW_REQUIRED"
                partial_scans += 1
        except Exception as exc:
            failed_scans += 1
            status = "SCAN_INCOMPLETE_BLOCKED"
            result["scanner_status"]["failed_stage"] = phase
            result["scanner_status"]["error_type"] = type(exc).__name__
            # Preserve only a tightly constrained internal code; never include stdout/stderr or source excerpts.
            match = re.match(
                r"^(COMMAND_FAILED:[A-Za-z0-9_.-]+:exit=[0-9]+|[A-Z][A-Z0-9_]{2,80})$",
                str(exc),
            )
            error_code = match.group(1) if match else "AUDIT_STEP_FAILED"
            result["scanner_status"]["error_code"] = error_code
        finally:
            result["status"] = status
            result["finished_at_utc"] = utc_now()
            result_path = candidate_out / "candidate-audit.json"
            result_path.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            results.append(result)
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
            if scratch_dir.exists():
                shutil.rmtree(scratch_dir, ignore_errors=True)
            print(
                "CANDIDATE_FINISHED="
                + repository
                + " STATUS="
                + status
                + " FAILED_STAGE="
                + str(result.get("scanner_status", {}).get("failed_stage", "none"))
                + " ERROR_CODE="
                + str(result.get("scanner_status", {}).get("error_code", "none"))
                + " SEMGREP_COUNT="
                + str(result.get("finding_counts", {}).get("semgrep", "NA"))
                + " TRIVY_COUNT="
                + str(result.get("finding_counts", {}).get("trivy_total", "NA"))
            )

    finished_at = utc_now()
    completed = sum(1 for result in results if result["status"] == "SCAN_COMPLETE_HUMAN_REVIEW_REQUIRED")
    overall_status = (
        "AUDIT_INCOMPLETE_BLOCKED" if failed_scans
        else "AUDIT_COMPLETE_WITH_COVERAGE_LIMITATIONS_HUMAN_REVIEW_REQUIRED"
        if partial_scans
        else "AUDIT_COMPLETE_HUMAN_REVIEW_REQUIRED"
    )
    report = {
        "schema": "aurelia.external_candidate_audit_report.v1",
        "status": overall_status,
        "review_status": "HUMAN_REVIEW_REQUIRED",
        "promotion_approved": False,
        "created_at_utc": started_at,
        "completed_at_utc": finished_at,
        "source_manifest_sha256": sha256_file(args.manifest),
        "candidate_count": len(candidates),
        "candidate_scans_complete": completed,
        "candidate_scans_blocked": failed_scans,
        "candidate_scans_partial": partial_scans,
        "tool_images": tool_images,
        "execution_policy": {
            "candidate_dependencies_installed": False,
            "candidate_code_executed": False,
            "candidate_builds_run": False,
            "candidate_tests_run": False,
            "git_submodules_initialized": False,
            "raw_scanner_reports_uploaded": False,
            "secret_values_in_reports": False,
        },
        "candidates": results,
    }
    report_json = args.output_dir / "audit-summary.json"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = [
        "# External Candidate Static Audit Summary",
        "",
        "Status: " + overall_status,
        "",
        "This is a static-analysis inventory, not a security approval or approved dependency list.",
        "",
        "Candidates: " + str(len(candidates)),
        "Scans complete: " + str(completed),
        "Scans with coverage limitations: " + str(partial_scans),
        "Scans blocked/incomplete: " + str(failed_scans),
        "Candidate dependencies installed: no",
        "Candidate code/builds/tests executed: no",
        "Raw scanner reports uploaded: no",
        "Secret values written to reports: no",
        "",
        "| Repository | Pin verified | Semgrep findings | Trivy findings | Disposition |",
        "|---|---:|---:|---:|---|",
    ]
    for result in results:
        metadata = result.get("source_metadata") or {}
        counts = result.get("finding_counts") or {}
        semgrep_count = counts.get("semgrep", "NA")
        trivy_count = counts.get("trivy_total", "NA")
        md.append(
            "| "
            + str(result["repository"])
            + " | "
            + str(metadata.get("pin_verified", False))
            + " | "
            + str(semgrep_count)
            + " | "
            + str(trivy_count)
            + " | "
            + str(result["status"])
            + " |"
        )
    md.extend([
        "",
        "## Required human disposition",
        "",
        "No candidate is approved. Intake-BLOCKED candidates remain blocked; all other candidates remain UNREVIEWED. Partial Semgrep coverage is recorded as a limitation, not a clean scan. Findings require manual triage, context validation, dependency/license review and independent security sign-off before any promotion. A zero-finding static report does not prove absence of vulnerabilities.",
    ])
    report_md = args.output_dir / "audit-summary.md"
    report_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    artifacts = []
    for path in sorted(args.output_dir.rglob("*")):
        if path.is_file():
            artifacts.append({
                "path": str(path.relative_to(args.output_dir)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    hashes_path = args.output_dir / "audit-artifact-hashes.json"
    hashes_path.write_text(json.dumps({
        "created_at_utc": utc_now(),
        "artifact_count_excluding_this_file": len(artifacts),
        "artifacts": artifacts,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("AUDIT_RESULT=" + overall_status)
    print("CANDIDATES_TOTAL=" + str(len(candidates)))
    print("SCANS_COMPLETE=" + str(completed))
    print("SCANS_PARTIAL=" + str(partial_scans))
    print("SCANS_BLOCKED=" + str(failed_scans))
    print("AUDIT_SUMMARY_SHA256=" + sha256_file(report_json))
    print("AUDIT_MARKDOWN_SHA256=" + sha256_file(report_md))
    print("ARTIFACT_HASH_MANIFEST_SHA256=" + sha256_file(hashes_path))
    return audit_exit_code(failed_scans=failed_scans, partial_scans=partial_scans)


if __name__ == "__main__":
    sys.exit(main())
