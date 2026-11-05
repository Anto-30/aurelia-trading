from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from enum import Enum
from math import isfinite
from typing import Any

DEFAULT_MAX_TRADE_RISK_FRACTION = 0.01
DEFAULT_MINIMUM_STAKE = 1.00
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class StakeSizingResult:
    allowed: bool
    stake: float | None
    risk_budget: float | None
    reason: str


def size_stake_for_balance(
    verified_available_balance: Any,
    *,
    maximum_risk_fraction: float = DEFAULT_MAX_TRADE_RISK_FRACTION,
    minimum_stake: float = DEFAULT_MINIMUM_STAKE,
) -> StakeSizingResult:
    """Size a purchased contract to at most 1% of fresh available capital.

    Deriv purchased-contract stake is treated as the contractual maximum loss.
    Risk budget is rounded down to cents. If that budget cannot fund the
    broker's minimum stake, no live stake is returned; the minimum is never
    forced above the account's risk budget.
    """
    if isinstance(verified_available_balance, bool) or not isinstance(
        verified_available_balance, (int, float, Decimal)
    ):
        return StakeSizingResult(False, None, None, "AVAILABLE_BALANCE_INVALID")
    try:
        balance_value = float(verified_available_balance)
    except (TypeError, ValueError, OverflowError):
        return StakeSizingResult(False, None, None, "AVAILABLE_BALANCE_INVALID")
    if not isfinite(balance_value) or balance_value < 0:
        return StakeSizingResult(False, None, None, "AVAILABLE_BALANCE_INVALID")

    if isinstance(maximum_risk_fraction, bool) or not isinstance(
        maximum_risk_fraction, (int, float, Decimal)
    ):
        return StakeSizingResult(False, None, None, "MAX_TRADE_RISK_FRACTION_INVALID")
    try:
        fraction_value = float(maximum_risk_fraction)
    except (TypeError, ValueError, OverflowError):
        return StakeSizingResult(False, None, None, "MAX_TRADE_RISK_FRACTION_INVALID")
    if not isfinite(fraction_value) or not 0 < fraction_value <= 0.02:
        return StakeSizingResult(False, None, None, "MAX_TRADE_RISK_FRACTION_INVALID")

    if isinstance(minimum_stake, bool) or not isinstance(
        minimum_stake, (int, float, Decimal)
    ):
        return StakeSizingResult(False, None, None, "MINIMUM_STAKE_INVALID")
    try:
        minimum_value = float(minimum_stake)
    except (TypeError, ValueError, OverflowError):
        return StakeSizingResult(False, None, None, "MINIMUM_STAKE_INVALID")
    if not isfinite(minimum_value) or minimum_value <= 0:
        return StakeSizingResult(False, None, None, "MINIMUM_STAKE_INVALID")

    try:
        balance = Decimal(str(verified_available_balance))
        fraction = Decimal(str(maximum_risk_fraction))
        minimum = Decimal(str(minimum_stake)).quantize(_CENT, rounding=ROUND_UP)
        budget = (balance * fraction).quantize(_CENT, rounding=ROUND_DOWN)
    except (InvalidOperation, ValueError, OverflowError):
        return StakeSizingResult(False, None, None, "STAKE_SIZING_INPUT_INVALID")

    if budget < minimum:
        return StakeSizingResult(
            False,
            None,
            float(budget),
            "STAKE_RISK_BUDGET_BELOW_BROKER_MINIMUM",
        )

    # With a validated risk fraction <= 2%, the budget is below available
    # balance. Keep this assertion as a fail-closed defense against future edits.
    if budget > balance:
        return StakeSizingResult(False, None, float(budget), "STAKE_EXCEEDS_AVAILABLE_BALANCE")

    return StakeSizingResult(
        True,
        float(budget),
        float(budget),
        "BALANCE_SCALED_WITHIN_RISK_BUDGET",
    )


# Stake-policy provenance is separate from numeric sizing. The registry never
# changes DEFAULT_MAX_TRADE_RISK_FRACTION or DEFAULT_MINIMUM_STAKE.

class CapitalPlane(str, Enum):
    LIVE = "LIVE"
    SHADOW = "SHADOW"
    RESEARCH = "RESEARCH"


class StakePolicyStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class StakePolicyRecord:
    """Source and approval provenance for one policy candidate.

    Missing provenance is represented as None and remains non-authoritative.
    A commit hash establishes a source revision; it is not an approval signature.
    """
    stake_value: float
    source_document: str | None
    source_commit: str | None
    approval_authority: str | None
    approval_date: datetime | None
    effective_date: datetime | None
    intended_capital_plane: CapitalPlane | None
    rationale: str | None
    validation_status: StakePolicyStatus = StakePolicyStatus.PENDING

    def has_valid_stake_value(self) -> bool:
        if isinstance(self.stake_value, bool) or not isinstance(
            self.stake_value, (int, float, Decimal)
        ):
            return False
        try:
            value = float(self.stake_value)
        except (TypeError, ValueError, OverflowError):
            return False
        return isfinite(value) and value > 0

    @staticmethod
    def _valid_utc(value: datetime | None) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() == timezone.utc.utcoffset(value)
        )

    def provenance_gaps(self) -> tuple[str, ...]:
        gaps: list[str] = []
        if not self.has_valid_stake_value():
            gaps.append("STAKE_VALUE_INVALID")
        if not isinstance(self.source_document, str) or not self.source_document.strip():
            gaps.append("SOURCE_DOCUMENT_MISSING")
        if (
            not isinstance(self.source_commit, str)
            or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", self.source_commit) is None
        ):
            gaps.append("SOURCE_COMMIT_MISSING_OR_INVALID")
        if not isinstance(self.approval_authority, str) or not self.approval_authority.strip():
            gaps.append("APPROVAL_AUTHORITY_MISSING")
        if not self._valid_utc(self.approval_date):
            gaps.append("APPROVAL_DATE_MISSING_OR_NON_UTC")
        if not self._valid_utc(self.effective_date):
            gaps.append("EFFECTIVE_DATE_MISSING_OR_NON_UTC")
        if not isinstance(self.intended_capital_plane, CapitalPlane):
            gaps.append("CAPITAL_PLANE_MISSING")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            gaps.append("RATIONALE_MISSING")
        if not isinstance(self.validation_status, StakePolicyStatus):
            gaps.append("VALIDATION_STATUS_INVALID")
        return tuple(gaps)

    def is_fully_documented(self) -> bool:
        return not self.provenance_gaps()


class StakePolicyReconciliationRegistry:
    """Fail-closed registry for sourced policy candidates and approvals."""

    def __init__(self) -> None:
        self._policies: list[StakePolicyRecord] = []

    def record_candidate(self, policy: StakePolicyRecord) -> None:
        """Record an unresolved candidate without making it authoritative."""
        if not isinstance(policy, StakePolicyRecord) or not policy.has_valid_stake_value():
            raise ValueError("STAKE_POLICY_CANDIDATE_INVALID")
        self._policies.append(policy)

    def register_policy(self, policy: StakePolicyRecord) -> None:
        """Register a documented policy; incomplete provenance is rejected."""
        if not isinstance(policy, StakePolicyRecord) or not policy.is_fully_documented():
            gaps = policy.provenance_gaps() if isinstance(policy, StakePolicyRecord) else ("POLICY_TYPE_INVALID",)
            raise ValueError("STAKE_POLICY_PROVENANCE_INCOMPLETE:" + ",".join(gaps))
        self._policies.append(policy)

    def get_authoritative_policy(
        self,
        capital_plane: CapitalPlane,
    ) -> StakePolicyRecord | None:
        candidates = [
            policy for policy in self._policies
            if policy.intended_capital_plane == capital_plane
            and policy.validation_status is StakePolicyStatus.VALIDATED
            and policy.is_fully_documented()
        ]
        if not candidates:
            return None
        if len(candidates) > 1:
            raise ValueError(
                f"MULTIPLE_VALIDATED_STAKE_POLICIES_FOR_{capital_plane.value}"
            )
        return candidates[0]

    def export_reconciliation_report(self) -> dict[str, Any]:
        rows = []
        for policy in self._policies:
            gaps = policy.provenance_gaps()
            rows.append({
                "stake_value": float(policy.stake_value),
                "source_document": policy.source_document,
                "source_commit": policy.source_commit,
                "approval_authority": policy.approval_authority,
                "approval_date": policy.approval_date.isoformat() if policy.approval_date else None,
                "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
                "intended_capital_plane": (
                    policy.intended_capital_plane.value
                    if isinstance(policy.intended_capital_plane, CapitalPlane) else None
                ),
                "rationale": policy.rationale,
                "validation_status": (
                    policy.validation_status.value
                    if isinstance(policy.validation_status, StakePolicyStatus) else "INVALID"
                ),
                "authoritative": not gaps and policy.validation_status is StakePolicyStatus.VALIDATED,
                "provenance_gaps": list(gaps),
            })
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "policy_count": len(rows),
            "authoritative_policy_count": sum(1 for row in rows if row["authoritative"]),
            "policies": rows,
        }
