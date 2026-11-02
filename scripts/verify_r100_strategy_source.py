from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

COLLECTOR_PATH = "research/r100_prospective_oos_collector.py"
ENGINE_PATH = "runtime/strategy/autonomous_signal_engine.py"

COLLECTOR_NODE_NAMES = {
    "PendingSignal",
    "research_config_hash",
    "legacy_research_config_hash",
    "build_signal_id",
    "observe_tick",
    "probability_metrics",
    "quoted_contract_economics",
    "evaluation",
}
ENGINE_NODE_NAMES = {"SignalCandidate", "AutonomousSignalHunter"}
STRATEGY_CONSTANTS = {
    "SYMBOL",
    "CURRENCY",
    "STRATEGY_ID",
    "STRATEGY_VERSION",
    "REGIME",
    "HORIZON_TICKS",
    "MIN_TRADE_PROBABILITY",
    "MAX_TRADE_PROBABILITY",
    "CALIBRATION_MIN_BUCKETS",
    "CALIBRATION_MIN_BUCKET_SAMPLES",
    "CALIBRATION_MAX_RELIABILITY_GAP",
}


def _git_show(reference_commit: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{reference_commit}:{path}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def _assignment_names(node: ast.AST) -> set[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    names: set[str] = set()
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.add(child.id)
    return names


def _strip_operational_evaluation_fields(node: ast.AST) -> ast.AST:
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            pairs = [
                (key, value)
                for key, value in zip(child.keys, child.values)
                if not (
                    isinstance(key, ast.Constant)
                    and key.value == "transport_reconnect_count"
                )
            ]
            child.keys = [key for key, _ in pairs]
            child.values = [value for _, value in pairs]
    return node


def _selected_ast(source: str, *, path: str) -> dict[str, str]:
    tree = ast.parse(source, filename=path)
    selected: dict[str, str] = {}
    if path == COLLECTOR_PATH:
        wanted_nodes = COLLECTOR_NODE_NAMES
    elif path == ENGINE_PATH:
        wanted_nodes = ENGINE_NODE_NAMES
    else:
        raise ValueError(f"Unsupported strategy source path: {path}")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name not in wanted_nodes:
                continue
            if node.name == "evaluation":
                node = _strip_operational_evaluation_fields(node)
            selected[node.name] = ast.dump(node, include_attributes=False)
        elif path == COLLECTOR_PATH:
            names = _assignment_names(node)
            for name in sorted(names & STRATEGY_CONSTANTS):
                selected[f"constant:{name}"] = ast.dump(node, include_attributes=False)

    required = {
        *(f"constant:{name}" for name in STRATEGY_CONSTANTS),
        *(name for name in wanted_nodes),
    }
    missing = sorted(required - set(selected))
    if missing:
        raise ValueError(f"R100_STRATEGY_SOURCE_NODES_MISSING:{','.join(missing)}")
    return selected


def strategy_source_hash(reference_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", reference_commit):
        raise ValueError("R100_REFERENCE_COMMIT_INVALID")

    current_collector = Path(COLLECTOR_PATH).read_text(encoding="utf-8")
    current_engine = Path(ENGINE_PATH).read_text(encoding="utf-8")
    reference_collector = _git_show(reference_commit, COLLECTOR_PATH)
    reference_engine = _git_show(reference_commit, ENGINE_PATH)

    current = {
        COLLECTOR_PATH: _selected_ast(current_collector, path=COLLECTOR_PATH),
        ENGINE_PATH: _selected_ast(current_engine, path=ENGINE_PATH),
    }
    reference = {
        COLLECTOR_PATH: _selected_ast(reference_collector, path=COLLECTOR_PATH),
        ENGINE_PATH: _selected_ast(reference_engine, path=ENGINE_PATH),
    }

    if current != reference:
        changed = []
        for path in (COLLECTOR_PATH, ENGINE_PATH):
            names = set(current[path]) | set(reference[path])
            changed.extend(
                f"{path}:{name}"
                for name in sorted(names)
                if current[path].get(name) != reference[path].get(name)
            )
        raise ValueError(
            "R100_STRATEGY_SOURCE_MISMATCH:" + ",".join(changed)
        )

    payload = json.dumps(current, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    print(strategy_source_hash(args.reference_commit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
