from __future__ import annotations

import ast
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.agent_worker_probe import ADVISORY_WORKERS, main


def test_ci_probe_reports_provider_connectivity_as_unverified() -> None:
    output = StringIO()
    with redirect_stdout(output):
        exit_code = main()

    report = output.getvalue()
    assert exit_code == 0
    assert "AGENT_PROVIDER_CONNECTIVITY=NOT_VERIFIED" in report
    assert "AGENT_PROVIDER_CONNECTED=NONE_CONFIRMED" in report
    assert "AGENT_PROVIDER_NOT_VERIFIED=" + ",".join(sorted(ADVISORY_WORKERS)) in report
    assert "AGENT_WORKER_PROCESS_LEASES=NOT_PROBED_IN_CI" in report
    assert "AGENT_WORKER_TASK_EVIDENCE=NOT_VERIFIED" in report
    assert "AGENT_WORKER_ACTIVE=" not in report


def test_ci_probe_cannot_launch_or_heartbeat_agent_workers() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts" / "agent_worker_probe.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert not any(
        module.startswith("runtime.agent_federation")
        or module.startswith("runtime.agent_workers")
        for module in imported_modules
    )
    assert "workers.start()" not in source
    assert "federation.heartbeat(" not in source
