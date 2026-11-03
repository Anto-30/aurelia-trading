"""Inert stake-policy provenance registry.

This module is an assurance inventory only. It does not set stake sizes,
authorize capital, or replace runtime/core/stake_sizing.py.
A record cannot be VALIDATED unless its original source commit, approval,
effective date and intended capital plane are independently documented.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import math
import re
from typing import Iterable


class CapitalPlane(str, Enum):
    RESEARCH = "RESEARCH"
    SHADOW_PAPER = "SHADOW_PAPER"
    LIVE = "LIVE"
    HISTORICAL = "HISTORICAL"
    DEPRECATED = "DEPRECATED"
    UNKNOWN = "UNKNOWN"


class ValidationStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True)
class StakePolicyRecord:
    policy_id: str
    version: str
    stake_usd: float
    role: str
    source_documents: tuple[str, ...]
    source_modified_at_utc: str | None
    source_commit: str | None
    observed_at_commit: str | None
    approval_authority: str | None
    approval_date: str | None
    effective_date: str | None
    intended_capital_plane: CapitalPlane
    rationale: str
    validation_status: ValidationStatus = ValidationStatus.PENDING

    def missing_provenance(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.policy_id.strip():
            missing.append("policy_id")
        if not self.version.strip():
            missing.append("version")
        if not math.isfinite(self.stake_usd) or self.stake_usd <= 0:
            missing.append("stake_usd")
        if not self.role.strip():
            missing.append("role")
        if not self.source_documents or any(not value.strip() for value in self.source_documents):
            missing.append("source_documents")
        if not self.source_modified_at_utc or not _valid_timestamp(self.source_modified_at_utc):
            missing.append("source_modified_at_utc")
        if not _valid_commit(self.source_commit):
            missing.append("source_commit")
        if not _valid_commit(self.observed_at_commit):
            missing.append("observed_at_commit")
        if not self.approval_authority or not self.approval_authority.strip():
            missing.append("approval_authority")
        if not self.approval_date or not _valid_date_or_timestamp(self.approval_date):
            missing.append("approval_date")
        if not self.effective_date or not _valid_date_or_timestamp(self.effective_date):
            missing.append("effective_date")
        if self.intended_capital_plane is CapitalPlane.UNKNOWN:
            missing.append("intended_capital_plane")
        if not self.rationale.strip():
            missing.append("rationale")
        return tuple(missing)

    def is_fully_documented(self) -> bool:
        return not self.missing_provenance()

    def validate_for_registry(self) -> None:
        if not self.policy_id.strip() or not self.version.strip():
            raise ValueError("STAKE_POLICY_ID_OR_VERSION_MISSING")
        if isinstance(self.stake_usd, bool) or not isinstance(self.stake_usd, (int, float)):
            raise ValueError("STAKE_POLICY_VALUE_INVALID")
        if not math.isfinite(float(self.stake_usd)) or self.stake_usd <= 0:
            raise ValueError("STAKE_POLICY_VALUE_INVALID")
        if self.validation_status is ValidationStatus.VALIDATED and not self.is_fully_documented():
            raise ValueError("VALIDATED_STAKE_POLICY_MISSING_PROVENANCE")


def _valid_commit(value: str | None) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _valid_timestamp(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _valid_date_or_timestamp(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        if len(value) == 10:
            date.fromisoformat(value)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return False
    except ValueError:
        return False
    return True


class StakePolicyReconciliationRegistry:
    """Read-only provenance inventory; it has no sizing or execution methods."""

    def __init__(self, records: Iterable[StakePolicyRecord] = ()) -> None:
        self._records: dict[str, StakePolicyRecord] = {}
        for record in records:
            self.register_policy(record)

    def register_policy(self, policy: StakePolicyRecord) -> None:
        policy.validate_for_registry()
        if policy.policy_id in self._records:
            raise ValueError("DUPLICATE_STAKE_POLICY_ID")
        self._records[policy.policy_id] = policy

    def get_authoritative_policy(
        self, capital_plane: CapitalPlane
    ) -> StakePolicyRecord | None:
        """Return one independently validated record, or None when unresolved."""
        candidates = [
            policy for policy in self._records.values()
            if policy.intended_capital_plane is capital_plane
            and policy.validation_status is ValidationStatus.VALIDATED
            and policy.is_fully_documented()
        ]
        if len(candidates) > 1:
            raise ValueError("MULTIPLE_VALIDATED_STAKE_POLICIES_FOR_CAPITAL_PLANE")
        return candidates[0] if candidates else None

    def export_reconciliation_report(self) -> dict:
        records = sorted(self._records.values(), key=lambda item: (item.stake_usd, item.policy_id))
        return {
            "schema": "aurelia.stake_policy_provenance.v1",
            "capital_authority": False,
            "runtime_policy_mutation": False,
            "policy_selection_performed": False,
            "total_policies": len(records),
            "fully_documented": sum(item.is_fully_documented() for item in records),
            "validated": sum(item.validation_status is ValidationStatus.VALIDATED for item in records),
            "pending": sum(item.validation_status is ValidationStatus.PENDING for item in records),
            "policies": [
                {
                    "policy_id": item.policy_id,
                    "version": item.version,
                    "stake_usd": item.stake_usd,
                    "role": item.role,
                    "source_documents": list(item.source_documents),
                    "source_modified_at_utc": item.source_modified_at_utc,
                    "source_commit": item.source_commit,
                    "observed_at_commit": item.observed_at_commit,
                    "approval_authority": item.approval_authority,
                    "approval_date": item.approval_date,
                    "effective_date": item.effective_date,
                    "intended_capital_plane": item.intended_capital_plane.value,
                    "rationale": item.rationale,
                    "validation_status": item.validation_status.value,
                    "missing_provenance": list(item.missing_provenance()),
                }
                for item in records
            ],
        }
