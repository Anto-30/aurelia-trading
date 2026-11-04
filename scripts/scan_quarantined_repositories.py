from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "external_repo_federation.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "quarantined_repo_source_scan.json"
MAX_TEXT_BYTES = 2 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 180

MANIFEST_NAMES = {
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg",
    "setup.py", "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "bun.lockb", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "Gemfile", "Gemfile.lock", "pom.xml", "build.gradle", "build.gradle.kts",
    "gradle.lockfile", "composer.json", "composer.lock",
}
SECURITY_NAMES = {
    "SECURITY", "SECURITY.md", "SECURITY.txt", "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md", "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING",
}
INSTALL_NAMES = {
    "install.sh", "setup.sh", "bootstrap.sh", "install.py", "setup.py",
    "configure", "configure.sh",
}
TEXT_SUFFIXES = {
    ".py", ".pyi", ".sh", ".bash", ".zsh", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".md", ".txt", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".ps1",
    ".bat", ".cmd", ".sql", ".tf", ".hcl", ".dockerfile",
}
SECRET_PATTERNS = (
    ("GITHUB_TOKEN_LIKE", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GITHUB_FINE_GRAINED_TOKEN_LIKE", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OPENAI_KEY_LIKE", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("AWS_ACCESS_KEY_LIKE", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY_HEADER", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "ASSIGNED_SECRET_LIKE",
        re.compile(r"""(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["'][^"'\s]{16,}["']"""),
    ),
)


def scan_secret_indicators(text: str) -> list[dict[str, Any]]:
    """Return only file-independent rule/line indicators; never return matched text."""
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for rule, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"line": line_number, "rule": rule})
    return findings


def scan_workflow_indicators(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if "pull_request_target" in line:
            findings.append({"line": line_number, "rule": "PULL_REQUEST_TARGET"})
        if re.match(r"^permissions:\s*write-all\s*$", stripped):
            findings.append({"line": line_number, "rule": "WRITE_ALL_PERMISSIONS"})
        if re.search(r"\buses:\s*[^\s#]+@(?:v\d+|main|master|latest)\b", line):
            findings.append({"line": line_number, "rule": "ACTION_REF_NOT_SHA_PINNED"})
        if re.search(r"\b(?:curl|wget)\b.*\|\s*(?:sh|bash)\b", line):
            findings.append({"line": line_number, "rule": "REMOTE_SCRIPT_PIPE_TO_SHELL"})
        if "persist-credentials: true" in line:
            findings.append({"line": line_number, "rule": "CHECKOUT_CREDENTIAL_PERSISTENCE"})
    return findings


def _git(repo_dir: Path, *args: str) -> str:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    command = [
        "git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "protocol.file.allow=never",
        "-c", "submodule.recurse=false",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=repo_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("GIT_OPERATION_FAILED")
    return result.stdout.strip()


def scan_repository(entry: dict[str, Any], workspace: Path) -> dict[str, Any]:
    repo = entry["repo"]
    pin = entry.get("head_commit")
    if not isinstance(pin, str) or not re.fullmatch(r"[0-9a-f]{40}", pin):
        return {"repo": repo, "status": "SKIPPED_UNRESOLVED_PIN"}

    repo_dir = workspace / repo.replace("/", "__")
    repo_dir.mkdir(parents=True, exist_ok=False)
    _git(repo_dir, "init", "--quiet")
    _git(repo_dir, "remote", "add", "origin", f"https://github.com/{repo}.git")
    _git(repo_dir, "fetch", "--depth=1", "--no-tags", "--filter=blob:none", "origin", pin)
    _git(repo_dir, "checkout", "--quiet", "--detach", "FETCH_HEAD")
    actual = _git(repo_dir, "rev-parse", "HEAD")
    if actual != pin:
        raise RuntimeError("CHECKED_OUT_COMMIT_MISMATCH")

    names_raw = _git(repo_dir, "ls-tree", "-r", "--name-only", "-z", "HEAD")
    paths = [value for value in names_raw.split("\x00") if value]
    manifests: list[str] = []
    security_docs: list[str] = []
    install_scripts: list[str] = []
    workflow_paths: list[str] = []
    lifecycle_hooks: list[dict[str, Any]] = []
    secret_indicators: list[dict[str, Any]] = []
    workflow_indicators: list[dict[str, Any]] = []

    for relative in paths:
        path = Path(relative)
        name = path.name
        lower = relative.lower()
        if name in MANIFEST_NAMES:
            manifests.append(relative)
        if name in SECURITY_NAMES:
            security_docs.append(relative)
        if name in INSTALL_NAMES:
            install_scripts.append(relative)
        if lower.startswith(".github/workflows/") and lower.endswith((".yml", ".yaml")):
            workflow_paths.append(relative)

        file_path = repo_dir / path
        try:
            if file_path.is_symlink() or not file_path.is_file():
                continue
            if file_path.stat().st_size > MAX_TEXT_BYTES:
                continue
            if file_path.suffix.lower() not in TEXT_SUFFIXES and name not in {
                "Dockerfile", "Makefile", ".gitmodules", ".gitattributes"
            }:
                continue
            raw = file_path.read_bytes()
            if b"\x00" in raw:
                continue
            text = raw.decode("utf-8", errors="replace")
        except OSError:
            continue

        for finding in scan_secret_indicators(text):
            secret_indicators.append({"path": relative, **finding})
        if relative in workflow_paths:
            for finding in scan_workflow_indicators(text):
                workflow_indicators.append({"path": relative, **finding})

        if name == "package.json":
            try:
                package = json.loads(text)
                scripts = package.get("scripts", {})
                if isinstance(scripts, dict):
                    for hook in ("preinstall", "install", "postinstall", "prepare"):
                        if isinstance(scripts.get(hook), str) and scripts[hook].strip():
                            lifecycle_hooks.append({"path": relative, "hook": hook})
            except (ValueError, TypeError):
                lifecycle_hooks.append({"path": relative, "hook": "PACKAGE_JSON_PARSE_ERROR"})

    return {
        "repo": repo,
        "status": "CLONED_AND_SCANNED",
        "mode": entry.get("mode"),
        "license_metadata": entry.get("license_metadata"),
        "pinned_commit": pin,
        "checked_out_commit": actual,
        "file_count": len(paths),
        "dependency_manifest_paths": sorted(manifests),
        "security_document_paths": sorted(security_docs),
        "installer_paths": sorted(install_scripts),
        "workflow_paths": sorted(workflow_paths),
        "package_lifecycle_hooks": lifecycle_hooks,
        "workflow_risk_indicators": workflow_indicators,
        "secret_indicators": secret_indicators,
        "secret_indicator_count": len(secret_indicators),
        "repository_code_executed": False,
        "dependencies_installed": False,
        "submodules_initialized": False,
        "raw_secret_values_emitted": False,
    }


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    intake = registry["intake_2026_11_02_followup"]
    entries = {entry["repo"]: entry for entry in registry["repositories"]}
    targets = intake["repository_names"]
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="aurelia-quarantined-repos-") as tmp:
        workspace = Path(tmp)
        for repo in targets:
            entry = entries.get(repo)
            if entry is None:
                results.append({"repo": repo, "status": "MISSING_REGISTRY_ENTRY"})
                continue
            try:
                results.append(scan_repository(entry, workspace))
            except Exception as exc:
                results.append({
                    "repo": repo,
                    "status": "CLONE_OR_SCAN_FAILED",
                    "error_class": type(exc).__name__,
                    "raw_error_emitted": False,
                })

    completed = sum(item["status"] == "CLONED_AND_SCANNED" for item in results)
    report = {
        "schema": "aurelia.quarantined_repo_source_scan.v1",
        "date": "2026-11-02",
        "requested_repositories": len(targets),
        "completed_repositories": completed,
        "failed_or_skipped_repositories": len(results) - completed,
        "source_only_scan": True,
        "repository_code_executed": False,
        "dependencies_installed": False,
        "broker_access_performed": False,
        "production_secrets_accessed": False,
        "raw_secret_values_emitted": False,
        "results": results,
    }
    output = Path(os.getenv("AURELIA_REPO_SCAN_OUT", str(DEFAULT_OUTPUT)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"QUARANTINED_REPO_SCAN_COMPLETED={completed}")
    print(f"QUARANTINED_REPO_SCAN_FAILED_OR_SKIPPED={len(results) - completed}")
    print("REPOSITORY_CODE_EXECUTED=false")
    print("DEPENDENCIES_INSTALLED=false")
    print("PRODUCTION_SECRETS_ACCESSED=false")
    print("RAW_SECRET_VALUES_EMITTED=false")
    return 0 if completed == len(targets) else 1


if __name__ == "__main__":
    raise SystemExit(main())
