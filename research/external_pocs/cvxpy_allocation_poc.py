"""Offline, synthetic-data CVXPY proof of concept; never used by the AURELIA runtime."""
from __future__ import annotations

import hashlib
import json
import sys

import cvxpy as cp
import numpy as np

COVARIANCE = np.array(
    [
        [0.040, 0.006, 0.002],
        [0.006, 0.090, 0.008],
        [0.002, 0.008, 0.160],
    ],
    dtype=float,
)
TOLERANCE = 1e-5


def solve_min_variance(covariance: np.ndarray, max_weight: float = 0.65) -> dict:
    matrix = np.asarray(covariance, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] < 2:
        raise ValueError("COVARIANCE_MUST_BE_SQUARE")
    if not np.isfinite(matrix).all():
        raise ValueError("COVARIANCE_MUST_BE_FINITE")
    if not np.allclose(matrix, matrix.T, atol=1e-10, rtol=0):
        raise ValueError("COVARIANCE_MUST_BE_SYMMETRIC")
    if float(np.linalg.eigvalsh(matrix).min()) < -1e-9:
        raise ValueError("COVARIANCE_MUST_BE_POSITIVE_SEMIDEFINITE")
    if not np.isfinite(max_weight) or max_weight <= 0 or max_weight > 1:
        raise ValueError("MAX_WEIGHT_OUT_OF_RANGE")
    asset_count = matrix.shape[0]
    if asset_count * max_weight < 1 - 1e-12:
        raise ValueError("ALLOCATION_CONSTRAINTS_INFEASIBLE")

    weights = cp.Variable(asset_count)
    problem = cp.Problem(
        cp.Minimize(cp.quad_form(weights, cp.psd_wrap(matrix))),
        [weights >= 0, cp.sum(weights) == 1, weights <= max_weight],
    )
    problem.solve()
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or weights.value is None:
        raise RuntimeError(f"OPTIMIZER_REJECTED_STATUS:{problem.status}")

    solution = np.asarray(weights.value, dtype=float).reshape(-1)
    if not np.isfinite(solution).all():
        raise RuntimeError("OPTIMIZER_RETURNED_NONFINITE_WEIGHTS")
    if solution.min() < -TOLERANCE or solution.max() > max_weight + TOLERANCE:
        raise RuntimeError("OPTIMIZER_CONSTRAINT_VIOLATION")
    if abs(float(solution.sum()) - 1.0) > TOLERANCE:
        raise RuntimeError("OPTIMIZER_BUDGET_CONSTRAINT_VIOLATION")

    digest = hashlib.sha256(matrix.tobytes()).hexdigest()
    return {
        "status": problem.status,
        "solver": problem.solver_stats.solver_name,
        "objective_variance": float(problem.value),
        "weights": [float(x) for x in solution],
        "sum_weights": float(solution.sum()),
        "max_weight": float(solution.max()),
        "input_sha256": digest,
        "authority": "RESEARCH_ONLY_NO_ORDER_OR_LEDGER_ACCESS",
    }


def main() -> int:
    result = solve_min_variance(COVARIANCE)
    repeat = solve_min_variance(COVARIANCE)
    equal_weight = np.full(COVARIANCE.shape[0], 1 / COVARIANCE.shape[0])
    baseline = float(equal_weight @ COVARIANCE @ equal_weight)
    if not np.allclose(result["weights"], repeat["weights"], atol=TOLERANCE, rtol=0):
        raise AssertionError("SYNTHETIC_SOLVE_NOT_REPRODUCIBLE_WITHIN_TOLERANCE")
    if result["objective_variance"] > baseline + TOLERANCE:
        raise AssertionError("OPTIMIZER_DID_NOT_MATCH_FEASIBLE_EQUAL_WEIGHT_BASELINE")
    try:
        solve_min_variance(COVARIANCE, max_weight=0.2)
    except ValueError as exc:
        if str(exc) != "ALLOCATION_CONSTRAINTS_INFEASIBLE":
            raise
    else:
        raise AssertionError("INFEASIBLE_CONSTRAINTS_WERE_NOT_REJECTED")
    try:
        solve_min_variance(np.array([[1.0, 2.0], [2.0, 1.0]]))
    except ValueError as exc:
        if str(exc) != "COVARIANCE_MUST_BE_POSITIVE_SEMIDEFINITE":
            raise
    else:
        raise AssertionError("INVALID_COVARIANCE_WAS_NOT_REJECTED")
    result["equal_weight_baseline_variance"] = baseline
    result["validation"] = "PASS_SYNTHETIC_FIXTURE_ONLY"
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
